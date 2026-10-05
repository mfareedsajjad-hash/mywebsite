from django.contrib import admin
from .models import Category, Product, Order, OrderItem, UserProfile

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'wholesale_price', 'margin')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_phone', 'city', 'total_amount', 'total_profit', 'status', 'payment_method', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_method', 'payment_status', 'created_at')
    search_fields = ('customer_name', 'customer_phone', 'city')
    list_editable = ('status', 'payment_status')
    inlines = [OrderItemInline]

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'created_at', 'updated_at')
    search_fields = ('user__username', 'phone', 'city')
    list_filter = ('created_at',)

admin.site.register(Category)
admin.site.register(Product)