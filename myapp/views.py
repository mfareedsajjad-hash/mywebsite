from decimal import Decimal
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
from .models import Product, Category, Order, OrderItem, UserProfile


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
    
    # Get user profile data for pre-filling
    user_profile = None
    if request.user.is_authenticated:
        user_profile = getattr(request.user, 'profile', None)
    
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total_wholesale': total_wholesale,
        'total_reseller_profit': total_reseller_profit,
        'grand_total': grand_total,
        'error': error,
        'cart_count': cart_count,
        'user_profile': user_profile,
    })


def place_order(request):
    if request.method == 'POST':
        customer_name = request.POST.get('name', '').strip()
        customer_phone = request.POST.get('phone', '').strip()
        customer_address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        payment_method = request.POST.get('payment_method', 'COD')

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
            
            # Set payment status based on payment method
            payment_status = 'Paid' if payment_method != 'COD' else 'Pending'
            transaction_id = request.POST.get('transaction_id', '') if payment_method != 'COD' else None

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=customer_name,
                customer_phone=customer_phone,
                city=city,
                address=customer_address,
                total_amount=grand_total,
                total_profit=total_profit,
                payment_method=payment_method,
                payment_status=payment_status,
                transaction_id=transaction_id
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
                'payment_method': payment_method,
                'payment_status': payment_status,
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
                'payment_method': payment_method,
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
        UserProfile.objects.create(user=user)
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


@login_required
def user_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update user info
        request.user.email = request.POST.get('email', request.user.email)
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.save()
        
        # Update profile info
        profile.phone = request.POST.get('phone', '')
        profile.city = request.POST.get('city', '')
        profile.address = request.POST.get('address', '')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'profile.html', {
        'profile': profile,
        'user': request.user,
    })


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


@user_passes_test(is_superuser, login_url='/login/')
def admin_dashboard(request):
    # Time periods
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Total statistics
    total_orders = Order.objects.count()
    total_sales = Order.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_profit = Order.objects.aggregate(total=Sum('total_profit'))['total'] or Decimal('0')
    total_users = User.objects.count()
    total_products = Product.objects.count()
    
    # Today's statistics
    today_orders = Order.objects.filter(created_at__date=today).count()
    today_sales = Order.objects.filter(created_at__date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    today_profit = Order.objects.filter(created_at__date=today).aggregate(total=Sum('total_profit'))['total'] or Decimal('0')
    
    # Last 7 days statistics
    week_orders = Order.objects.filter(created_at__date__gte=last_7_days).count()
    week_sales = Order.objects.filter(created_at__date__gte=last_7_days).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    week_profit = Order.objects.filter(created_at__date__gte=last_7_days).aggregate(total=Sum('total_profit'))['total'] or Decimal('0')
    
    # Last 30 days statistics
    month_orders = Order.objects.filter(created_at__date__gte=last_30_days).count()
    month_sales = Order.objects.filter(created_at__date__gte=last_30_days).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    month_profit = Order.objects.filter(created_at__date__gte=last_30_days).aggregate(total=Sum('total_profit'))['total'] or Decimal('0')
    
    # Order status breakdown
    status_counts_queryset = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')
    
    # Recent orders (last 10)
    recent_orders = Order.objects.select_related('user').prefetch_related('items__product').order_by('-created_at')[:10]
    
    # Top selling products
    top_products = OrderItem.objects.values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum('wholesale_price') + Sum('margin')
    ).order_by('-total_quantity')[:5]
    
    # Top resellers (by profit)
    top_resellers = Order.objects.values('user__username').annotate(
        total_orders=Count('id'),
        total_profit=Sum('total_profit')
    ).exclude(user__username__isnull=True).order_by('-total_profit')[:5]
    
    # Payment method breakdown
    payment_methods = Order.objects.values('payment_method').annotate(count=Count('id')).order_by('-count')
    
    # Payment status breakdown
    payment_status = Order.objects.values('payment_status').annotate(count=Count('id')).order_by('-count')
    
    # Average order value
    total_orders_count = Order.objects.count()
    if total_orders_count > 0:
        avg_order_value = total_sales / total_orders_count
    else:
        avg_order_value = Decimal('0')
    
    # Daily sales data for last 7 days
    daily_sales = []
    for i in range(7):
        date = today - timedelta(days=i)
        sales = Order.objects.filter(created_at__date=date).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        daily_sales.append({
            'date': date.strftime('%m/%d'),
            'sales': float(sales)
        })
    daily_sales.reverse()
    
    context = {
        # Total stats
        'total_orders': total_orders,
        'total_sales': total_sales,
        'total_profit': total_profit,
        'total_users': total_users,
        'total_products': total_products,
        'avg_order_value': avg_order_value,
        
        # Today's stats
        'today_orders': today_orders,
        'today_sales': today_sales,
        'today_profit': today_profit,
        
        # Week stats
        'week_orders': week_orders,
        'week_sales': week_sales,
        'week_profit': week_profit,
        
        # Month stats
        'month_orders': month_orders,
        'month_sales': month_sales,
        'month_profit': month_profit,
        
        # Status breakdown
        'status_counts': status_counts,
        
        # Recent activity
        'recent_orders': recent_orders,
        
        # Top products and resellers
        'top_products': top_products,
        'top_resellers': top_resellers,
        
        # Payment breakdown
        'payment_methods': payment_methods,
        'payment_status': payment_status,
        
        # Chart data
        'daily_sales': json.dumps(daily_sales),
        'status_counts': json.dumps(list(status_counts_queryset)),
        'status_counts_queryset': status_counts_queryset,
    }
    
    return render(request, 'admin_dashboard.html', context)