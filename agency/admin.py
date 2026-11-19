from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, DecimalField, F, Sum
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from import_export.admin import ExportMixin, ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import (FINISHED_STATUSES, Crew, CrewScheduleException, Order,
                     OrderItem, OrderStatus, Service, ServiceCategory, User)
from .resources import OrderResource, ServiceResource

admin.site.site_header = 'Агентство по ремонту квартир'
admin.site.site_title = 'Администрирование'
admin.site.index_title = 'Управление данными агентства'


# ---------- Пользователи ----------

@admin.register(User)
class AgencyUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('role', 'phone', 'crew', 'avatar')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительно', {'fields': ('role', 'phone', 'email')}),
    )
    list_display = ('username', 'full_name', 'email', 'role', 'crew', 'phone', 'is_active')
    list_display_links = ('username', 'full_name')
    list_filter = ('role', 'is_active', 'crew', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    date_hierarchy = 'date_joined'
    filter_horizontal = ('groups', 'user_permissions')
    raw_id_fields = ('crew',)
    readonly_fields = ('last_login', 'date_joined')

    @admin.display(description='ФИО', ordering='last_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'


# ---------- Справочники ----------

class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ('name', 'price', 'image')
    show_change_link = True


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'services_count', 'image_preview')
    list_display_links = ('name',)
    search_fields = ('name',)
    inlines = [ServiceInline]
    readonly_fields = ('image_preview',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_services=Count('services'))

    @admin.display(description='Услуг в категории', ordering='_services')
    def services_count(self, obj):
        return obj._services

    @admin.display(description='Превью')
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px">', obj.image.url)
        return '—'


@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('sort_order', 'name', 'orders_count')
    list_display_links = ('name',)
    search_fields = ('name',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_orders=Count('orders'))

    @admin.display(description='Заказов', ordering='_orders')
    def orders_count(self, obj):
        return obj._orders


# ---------- Бригады ----------

class CrewMemberInline(admin.TabularInline):
    model = User
    fk_name = 'crew'
    extra = 0
    fields = ('username', 'first_name', 'last_name', 'phone')
    readonly_fields = ('username',)
    can_delete = False
    verbose_name = 'Мастер бригады'
    verbose_name_plural = 'Состав бригады'
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class CrewScheduleExceptionInline(admin.TabularInline):
    model = CrewScheduleException
    extra = 0
    fields = ('date_from', 'date_to', 'type', 'note')
    verbose_name = 'Период недоступности'
    verbose_name_plural = 'Расписание: отпуска, больничные, отгулы'


@admin.register(Crew)
class CrewAdmin(admin.ModelAdmin):
    list_display = ('name', 'foreman', 'members_count', 'state_today')
    list_display_links = ('name',)
    search_fields = ('name', 'foreman__last_name', 'foreman__username')
    raw_id_fields = ('foreman',)
    fields = ('name', 'foreman', 'schedule_overview')
    readonly_fields = ('schedule_overview',)
    inlines = [CrewMemberInline, CrewScheduleExceptionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_members=Count('members'))

    @admin.display(description='Мастеров', ordering='_members')
    def members_count(self, obj):
        return obj._members

    @admin.display(description='Сегодня')
    def state_today(self, obj):
        kind, label = obj.state_on(timezone.localdate())
        color = {'free': '#198754', 'order': '#0d6efd', 'off': '#dc3545'}[kind]
        return format_html('<span style="color:{}">● {}</span>', color, label)

    @admin.display(description='Ближайшая занятость')
    def schedule_overview(self, obj):
        if not obj.pk:
            return '—'
        today = timezone.localdate()
        orders = (obj.orders.exclude(status__name__in=FINISHED_STATUSES)
                  .filter(start_date__isnull=False, duration_days__isnull=False)
                  .select_related('status'))
        rows = [(o.start_date, f'Заказ №{o.pk}: {o.start_date:%d.%m.%Y} – {o.end_date:%d.%m.%Y}')
                for o in orders if o.end_date >= today]
        rows += [(e.date_from, f'{e.get_type_display()}: {e.date_from:%d.%m.%Y} – {e.date_to:%d.%m.%Y}')
                 for e in obj.exceptions.filter(date_to__gte=today)]
        if not rows:
            return 'Нет запланированных заказов и отсутствий'
        rows.sort(key=lambda r: r[0])
        return format_html('<ul style="margin:0;padding-left:1.2em">{}</ul>',
                           format_html_join('', '<li>{}</li>', ((text,) for _, text in rows)))


@admin.register(CrewScheduleException)
class CrewScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = ('crew', 'type', 'date_from', 'date_to', 'note')
    list_display_links = ('crew',)
    list_filter = ('type', 'crew')
    search_fields = ('crew__name', 'note')
    date_hierarchy = 'date_from'


# ---------- Услуги ----------

@admin.register(Service)
class ServiceAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    resource_classes = [ServiceResource]
    history_list_display = ['price']
    list_display = ('name', 'category', 'price_rub', 'updated_at', 'updated_by')
    list_display_links = ('name',)
    list_filter = ('category', 'updated_at')
    search_fields = ('name', 'category__name')
    date_hierarchy = 'updated_at'
    raw_id_fields = ('updated_by',)
    readonly_fields = ('updated_at', 'updated_by')

    @admin.display(description='Цена', ordering='price')
    def price_rub(self, obj):
        return f'{obj.price:,.2f} ₽'.replace(',', ' ')

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ---------- Заказы ----------

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    raw_id_fields = ('service',)
    readonly_fields = ('line_total',)

    @admin.display(description='Сумма')
    def line_total(self, obj):
        if obj.pk:
            return obj.quantity * obj.unit_price
        return '—'


@admin.register(Order)
class OrderAdmin(ExportMixin, SimpleHistoryAdmin):
    resource_classes = [OrderResource]
    history_list_display = ['status', 'crew', 'total_cost']
    list_display = ('id', 'contact_name', 'contact_phone', 'status', 'crew', 'period',
                    'total_cost', 'is_overdue', 'created_at')
    list_select_related = ('status', 'crew')
    list_display_links = ('id', 'contact_name')
    list_filter = ('status', 'crew', 'created_at')
    search_fields = ('contact_name', 'contact_phone', 'client__username',
                     'client__last_name', 'manager__last_name')
    date_hierarchy = 'created_at'
    raw_id_fields = ('client', 'manager')
    readonly_fields = ('total_cost', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    fieldsets = (
        ('Заказчик', {'fields': ('client', 'contact_name', 'contact_phone')}),
        ('Исполнение', {'fields': ('status', 'manager', 'crew', 'start_date', 'duration_days')}),
        ('Итого', {'fields': ('total_cost', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Период работ')
    def period(self, obj):
        if obj.end_date:
            return f'{obj.start_date:%d.%m.%Y} – {obj.end_date:%d.%m.%Y}'
        return '—'

    @admin.display(description='Просрочен', boolean=True)
    def is_overdue(self, obj):
        end = obj.end_date
        return bool(end and end < timezone.localdate()
                    and obj.status.name not in FINISHED_STATUSES)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        order = form.instance
        total = order.items.aggregate(
            s=Sum(F('quantity') * F('unit_price'), output_field=DecimalField())
        )['s'] or 0
        # save() вместо update(), чтобы итоговая сумма попала в историю изменений
        order.total_cost = total
        order.save(update_fields=['total_cost', 'updated_at'])


@admin.register(OrderItem)
class OrderItemAdmin(SimpleHistoryAdmin):
    history_list_display = ['quantity', 'unit_price']
    list_display = ('id', 'order', 'service', 'quantity', 'unit_price')
    list_display_links = ('id', 'order')
    list_filter = ('service__category',)
    search_fields = ('order__contact_name', 'service__name')
    raw_id_fields = ('order', 'service')
