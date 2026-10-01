from decimal import Decimal
from django.shortcuts import render, redirect
from .models import Product, Category, Order, OrderItem

# ... (home_store, add_to_cart, remove_from_cart, cart views purane wale hi rahenge)

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