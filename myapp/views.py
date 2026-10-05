from decimal import Decimal
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from .models import Product, Category, Order, OrderItem


def home_store(request):
    query = request.GET.get('search', '').strip()
    products = Product.objects.select_related('category').order_by('-id')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(request, 'home.html', {
        'products': products,
        'categories': Category.objects.all(),
        'query': query,
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

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total_reseller_profit': total_reseller_profit,
        'grand_total': total_wholesale + total_reseller_profit,
    })


def place_order(request):
    if request.method == 'POST':
        customer_name = request.POST.get('name')
        customer_phone = request.POST.get('phone')
        customer_address = request.POST.get('address')
        city = request.POST.get('city')

        cart = request.session.get('cart', {})
        if not cart:
            return redirect('home')

        total_wholesale = Decimal('0')
        total_profit = Decimal('0')

        # Pehle totals calculate karein
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

        # Database me Order save karein
        order = Order.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            city=city,
            address=customer_address,
            total_amount=grand_total,
            total_profit=total_profit
        )

        # Order Items save karein
        for item in order_items_data:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                wholesale_price=item['wholesale_price'],
                margin=item['margin']
            )

        # Session Cart Khali Karein
        request.session['cart'] = {}

        return render(request, 'order_success.html', {
            'order_id': order.id,
            'name': customer_name,
            'phone': customer_phone,
            'address': customer_address,
            'city': city
        })
    return redirect('cart')