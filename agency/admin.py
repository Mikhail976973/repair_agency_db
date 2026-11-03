from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Order, OrderItem, OrderStatus, Service, ServiceCategory, User


@admin.register(User)
class AgencyUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Дополнительно', {'fields': ('phone', 'role', 'avatar')}),)
    list_display = ('username', 'email', 'role', 'phone')


admin.site.register(ServiceCategory)
admin.site.register(OrderStatus)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'updated_at')
    list_filter = ('category',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'contact_name', 'contact_phone', 'status', 'total_cost', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]
