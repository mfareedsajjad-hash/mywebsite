from decimal import Decimal
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Product, Category, Order, OrderItem


def home_store(request):
    query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category').order_by('-id')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    
    cart = request.session.get('cart', {})
    cart_count = sum(item.get('quantity', 0) for item in cart.values())
    
    return render(request, 'home.html', {
        'products': products,
        'categories': Category.objects.all(),
        'query': query,
        'category_id': category_id,
        'cart_count': cart_count,
    })


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        margin = max(Decimal(request.POST.get('margin') or '0'), Decimal('0'))
    except ArithmeticError:
        margin = Decimal('0')

    cart = request.session.get('cart', {})
    key = str(product.id)
    item = cart.get(key, {'quantity': 0})
    item['quantity'] += 1
    item['margin'] = str(margin)
    cart[key] = item
    request.session['cart'] = cart
    return redirect('cart')


def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    if cart.pop(str(product_id), None) is not None:
        request.session['cart'] = cart
    return redirect('cart')


def clear_cart(request):
    request.session['cart'] = {}
    return redirect('cart')


def update_cart_quantity(request, product_id):
    if request.method == 'POST':
        action = request.POST.get('action')
        cart = request.session.get('cart', {})
        key = str(product_id)
        
        if key in cart:
            if action == 'increase':
                cart[key]['quantity'] += 1
            elif action == 'decrease':
                if cart[key]['quantity'] > 1:
                    cart[key]['quantity'] -= 1
                else:
                    cart.pop(key)
            request.session['cart'] = cart
    return redirect('cart')


def cart(request):
    cart = request.session.get('cart', {})
    products = Product.objects.in_bulk([int(pid) for pid in cart])

    cart_items = []
    total_wholesale = Decimal('0')
    total_reseller_profit = Decimal('0')
    for product_id, item_data in cart.items():
        product = products.get(int(product_id))
        if product is None:
            continue
        quantity = item_data['quantity']
        margin = Decimal(str(item_data.get('margin', 0)))
        total_wholesale += product.price * quantity
        total_reseller_profit += margin * quantity
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'wholesale_price': product.price,
            'margin': margin,
            'final_item_price': (product.price + margin) * quantity,
        })

    cart_count = sum(item.get('quantity', 0) for item in cart.values())
    grand_total = total_wholesale + total_reseller_profit
    error = request.GET.get('error', '')
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total_wholesale': total_wholesale,
        'total_reseller_profit': total_reseller_profit,
        'grand_total': grand_total,
        'error': error,
        'cart_count': cart_count,
    })


def place_order(request):
    if request.method == 'POST':
        customer_name = request.POST.get('name', '').strip()
        customer_phone = request.POST.get('phone', '').strip()
        customer_address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()

        cart = request.session.get('cart', {})
        if not cart:
            return redirect('home')

        if not customer_name or not customer_phone or not customer_address or not city:
            return redirect('/cart/?error=Please fill in all required fields')

        if len(customer_phone) < 10:
            return redirect('/cart/?error=Please enter a valid phone number')

        if request.POST.get('confirm') == 'true':
            total_wholesale = Decimal('0')
            total_profit = Decimal('0')

            order_items_data = []
            for product_id, item_data in cart.items():
                try:
                    product = Product.objects.get(id=product_id)
                    quantity = item_data['quantity']
                    margin = Decimal(str(item_data.get('margin', 0)))
                    
                    total_wholesale += product.price * quantity
                    total_profit += margin * quantity

                    order_items_data.append({
                        'product': product,
                        'quantity': quantity,
                        'wholesale_price': product.price,
                        'margin': margin
                    })
                except Product.DoesNotExist:
                    continue

            grand_total = total_wholesale + total_profit

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=customer_name,
                customer_phone=customer_phone,
                city=city,
                address=customer_address,
                total_amount=grand_total,
                total_profit=total_profit
            )

            for item in order_items_data:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    wholesale_price=item['wholesale_price'],
                    margin=item['margin']
                )

            request.session['cart'] = {}

            return render(request, 'order_success.html', {
                'order_id': order.id,
                'name': customer_name,
                'phone': customer_phone,
                'address': customer_address,
                'city': city,
                'user': request.user,
            })
        else:
            cart_items = []
            products = Product.objects.in_bulk([int(pid) for pid in cart])
            total_wholesale = Decimal('0')
            total_reseller_profit = Decimal('0')
            
            for product_id, item_data in cart.items():
                product = products.get(int(product_id))
                if product is None:
                    continue
                quantity = item_data['quantity']
                margin = Decimal(str(item_data.get('margin', 0)))
                total_wholesale += product.price * quantity
                total_reseller_profit += margin * quantity
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'wholesale_price': product.price,
                    'margin': margin,
                    'final_item_price': (product.price + margin) * quantity,
                })
            
            return render(request, 'checkout_review.html', {
                'cart_items': cart_items,
                'total_wholesale': total_wholesale,
                'total_reseller_profit': total_reseller_profit,
                'grand_total': total_wholesale + total_reseller_profit,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'city': city,
                'address': customer_address,
            })
    return redirect('cart')


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created_at')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    total_amount = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_profit = orders.aggregate(total=Sum('total_profit'))['total'] or Decimal('0')
    pending_count = orders.filter(status='Pending').count()
    
    return render(request, 'order_history.html', {
        'orders': orders,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_amount': total_amount,
        'total_profit': total_profit,
        'pending_count': pending_count,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product').all()
    total_wholesale = sum(item.wholesale_price * item.quantity for item in order_items)
    return render(request, 'order_detail.html', {
        'order': order,
        'order_items': order_items,
        'total_wholesale': total_wholesale,
    })


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not username or not email or not password:
            messages.error(request, 'All fields are required')
            return redirect('register')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return redirect('register')

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return redirect('register')

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        messages.success(request, 'Registration successful!')
        return redirect('home')

    return render(request, 'register.html')


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please enter username and password')
            return redirect('login')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            next_page = request.GET.get('next', 'home')
            return redirect(next_page)
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('login')

    return render(request, 'login.html')


def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out')
    return redirect('home')