from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Order, Product


class StoreFlowTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='Watch', price=Decimal('1000'), description='Steel')

    def test_home_lists_and_searches_products(self):
        Product.objects.create(name='Shoes', price=Decimal('500'))
        response = self.client.get(reverse('home'), {'search': 'watch'})
        self.assertContains(response, 'Watch')
        self.assertNotContains(response, 'Shoes')

    def test_cart_and_place_order(self):
        url = reverse('add_to_cart', args=[self.product.id])
        self.client.post(url, {'margin': '200'})
        self.client.post(url, {'margin': '200'})

        response = self.client.get(reverse('cart'))
        self.assertEqual(response.context['grand_total'], Decimal('2400'))
        self.assertEqual(response.context['total_reseller_profit'], Decimal('400'))

        response = self.client.post(reverse('place_order'), {
            'name': 'Ali', 'phone': '03001234567', 'city': 'Lahore', 'address': 'Street 1',
        })
        self.assertContains(response, 'Order Successfully Placed')
        order = Order.objects.get()
        self.assertEqual(order.total_amount, Decimal('2400'))
        self.assertEqual(order.total_profit, Decimal('400'))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(self.client.session['cart'], {})

    def test_remove_from_cart(self):
        self.client.post(reverse('add_to_cart', args=[self.product.id]), {'margin': '100'})
        self.client.get(reverse('remove_from_cart', args=[self.product.id]))
        self.assertEqual(self.client.session['cart'], {})
