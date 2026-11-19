from django.utils import timezone
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Order, Service, ServiceCategory, User


class OrderResource(resources.ModelResource):
    """Выгрузка заказов в Excel (только экспорт)."""
    id = fields.Field(attribute='id', column_name='№ заказа')
    contact_name = fields.Field(attribute='contact_name', column_name='Контакт')
    contact_phone = fields.Field(attribute='contact_phone', column_name='Телефон')
    client = fields.Field(attribute='client', column_name='Клиент',
                          widget=ForeignKeyWidget(User, 'username'))
    manager = fields.Field(attribute='manager', column_name='Менеджер',
                           widget=ForeignKeyWidget(User, 'username'))
    crew = fields.Field(attribute='crew__name', column_name='Бригада')
    status = fields.Field(attribute='status__name', column_name='Статус')
    start_date = fields.Field(attribute='start_date', column_name='Начало работ')
    end_date = fields.Field(column_name='Окончание работ')
    duration_days = fields.Field(attribute='duration_days', column_name='Срок, дней')
    services = fields.Field(column_name='Услуги')
    total_cost = fields.Field(attribute='total_cost', column_name='Стоимость, ₽')
    created_at = fields.Field(attribute='created_at', column_name='Создан')

    class Meta:
        model = Order
        fields = ('id', 'contact_name', 'contact_phone', 'client', 'manager', 'crew',
                  'status', 'start_date', 'end_date', 'duration_days', 'services',
                  'total_cost', 'created_at')
        export_order = fields

    def get_queryset(self):
        return (super().get_queryset()
                .select_related('client', 'manager', 'crew', 'status')
                .prefetch_related('items__service'))

    # Числа и даты отдаём «как есть», чтобы в Excel они были числами и датами, а не текстом
    def dehydrate_start_date(self, obj):
        return obj.start_date

    def dehydrate_end_date(self, obj):
        return obj.end_date

    def dehydrate_duration_days(self, obj):
        return obj.duration_days

    def dehydrate_total_cost(self, obj):
        return obj.total_cost

    def dehydrate_created_at(self, obj):
        # Excel не поддерживает часовые пояса: переводим в локальное время без tzinfo
        return timezone.make_naive(obj.created_at)

    def dehydrate_services(self, obj):
        return '; '.join(f'{i.service.name} × {i.quantity.normalize():f}' for i in obj.items.all())


class ServiceResource(resources.ModelResource):
    """Прайс-лист: экспорт и импорт услуг (категория – по названию)."""
    id = fields.Field(attribute='id', column_name='id')
    category = fields.Field(attribute='category', column_name='Категория',
                            widget=ForeignKeyWidget(ServiceCategory, 'name'))
    name = fields.Field(attribute='name', column_name='Название')
    price = fields.Field(attribute='price', column_name='Цена, ₽')

    def dehydrate_price(self, obj):
        return obj.price

    class Meta:
        model = Service
        fields = ('id', 'category', 'name', 'price')
        export_order = fields
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = True
