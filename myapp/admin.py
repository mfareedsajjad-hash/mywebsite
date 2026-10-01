from django.contrib import admin
from .models import Category, Product, Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'wholesale_price', 'margin')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_phone', 'city', 'total_amount', 'total_profit', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer_name', 'customer_phone', 'city')
    list_editable = ('status',)  # Direct list se status change karne ke liye
    inlines = [OrderItemInline]

admin.site.register(Category)
admin.site.register(Product)