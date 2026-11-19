from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from simple_history.models import HistoricalRecords

# Статусы, в которых заказ больше не занимает бригаду
FINISHED_STATUSES = ('Сдан', 'Отменён')


class User(AbstractUser):
    """Клиенты и сотрудники (таблица users)."""

    class Role(models.TextChoices):
        CLIENT = 'client', 'Клиент'
        MANAGER = 'manager', 'Менеджер'
        WORKER = 'worker', 'Мастер'
        ADMIN = 'admin', 'Администратор'

    crew = models.ForeignKey('Crew', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='members', verbose_name='Бригада',
                             help_text='Для мастеров: бригада, в которой состоит')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    role = models.CharField('Роль', max_length=20, choices=Role.choices, default=Role.CLIENT)
    avatar = models.ImageField('Фото профиля', upload_to='avatars/', blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.get_full_name() or self.username


class Crew(models.Model):
    """Бригады мастеров."""
    name = models.CharField('Название', max_length=100, unique=True)
    foreman = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='led_crews', verbose_name='Бригадир')

    class Meta:
        verbose_name = 'Бригада'
        verbose_name_plural = 'Бригады'
        ordering = ['name']

    def __str__(self):
        return self.name

    def find_conflicts(self, start, end, exclude_order=None):
        """Заказы и периоды недоступности, пересекающиеся с [start, end] (включительно).

        Занятость заказами не хранится отдельно, а берётся из orders:
        период заказа — start_date ... start_date + duration_days - 1.
        """
        orders = (self.orders
                  .exclude(status__name__in=FINISHED_STATUSES)
                  .filter(start_date__isnull=False, duration_days__isnull=False,
                          start_date__lte=end)
                  .select_related('status'))
        if exclude_order is not None and exclude_order.pk:
            orders = orders.exclude(pk=exclude_order.pk)
        orders = [o for o in orders if o.end_date >= start]
        exceptions = list(self.exceptions.filter(date_from__lte=end, date_to__gte=start))
        return orders, exceptions

    def state_on(self, day):
        """Состояние бригады в указанный день: ('free' | 'order' | 'off', подпись)."""
        exception = self.exceptions.filter(date_from__lte=day, date_to__gte=day).first()
        if exception:
            return 'off', exception.get_type_display()
        orders, _ = self.find_conflicts(day, day)
        if orders:
            return 'order', f'Заказ №{orders[0].pk}'
        return 'free', 'Свободна'


class CrewScheduleException(models.Model):
    """Периоды, когда бригада недоступна: отпуск, больничный, отгул."""

    class Type(models.TextChoices):
        VACATION = 'vacation', 'Отпуск'
        SICK = 'sick', 'Больничный'
        DAY_OFF = 'day_off', 'Отгул'

    crew = models.ForeignKey(Crew, on_delete=models.CASCADE, related_name='exceptions',
                             verbose_name='Бригада')
    date_from = models.DateField('С даты')
    date_to = models.DateField('По дату (включительно)')
    type = models.CharField('Тип', max_length=20, choices=Type.choices, default=Type.VACATION)
    note = models.CharField('Примечание', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Период недоступности'
        verbose_name_plural = 'Расписание бригад (недоступность)'
        ordering = ['-date_from']
        indexes = [models.Index(fields=['crew', 'date_from', 'date_to'])]
        constraints = [
            models.CheckConstraint(condition=models.Q(date_to__gte=models.F('date_from')),
                                   name='crew_exception_dates_order'),
        ]

    def __str__(self):
        return f'{self.crew}: {self.get_type_display()} {self.date_from:%d.%m.%Y}–{self.date_to:%d.%m.%Y}'

    def clean(self):
        super().clean()
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValidationError({'date_to': 'Дата окончания не может быть раньше даты начала.'})


class ServiceCategory(models.Model):
    """Справочник категорий услуг."""
    name = models.CharField('Название', max_length=100, unique=True)
    image = models.ImageField('Изображение', upload_to='categories/', blank=True)

    class Meta:
        verbose_name = 'Категория услуг'
        verbose_name_plural = 'Категории услуг'
        ordering = ['name']

    def __str__(self):
        return self.name


class OrderStatus(models.Model):
    """Справочник статусов (этапов) заказа."""
    name = models.CharField('Название', max_length=50, unique=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Статус заказа'
        verbose_name_plural = 'Статусы заказов'
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class Service(models.Model):
    """Каталог услуг."""
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT,
                                 related_name='services', verbose_name='Категория')
    name = models.CharField('Название', max_length=150)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    image = models.ImageField('Изображение', upload_to='services/', blank=True)
    updated_at = models.DateTimeField('Изменено', auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name='Кто изменил')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('agency:service_detail', args=[self.id])


class Order(models.Model):
    """Заявки и заказы (заявка — заказ в начальном статусе)."""
    client = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='orders', verbose_name='Клиент')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='managed_orders', verbose_name='Менеджер')
    crew = models.ForeignKey(Crew, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='orders', verbose_name='Бригада')
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT,
                               related_name='orders', verbose_name='Статус')
    contact_name = models.CharField('Имя контакта', max_length=100)
    contact_phone = models.CharField('Телефон контакта', max_length=20)
    start_date = models.DateField('Дата начала работ', null=True, blank=True)
    duration_days = models.PositiveIntegerField('Срок, дней', null=True, blank=True)
    total_cost = models.DecimalField('Стоимость', max_digits=12, decimal_places=2, default=0)
    services = models.ManyToManyField(Service, through='OrderItem', related_name='orders',
                                      verbose_name='Услуги')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Изменено', auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return f'Заказ №{self.pk} — {self.contact_name}'

    @property
    def end_date(self):
        """Последний день работ (календарные дни, включительно); в БД не хранится."""
        if self.start_date and self.duration_days:
            return self.start_date + timedelta(days=self.duration_days - 1)
        return None

    def clean(self):
        super().clean()
        if self.duration_days is not None and self.duration_days < 1:
            raise ValidationError({'duration_days': 'Срок должен быть не меньше одного дня.'})
        if not self.crew_id:
            return
        if self.status_id and self.status.name in FINISHED_STATUSES:
            return
        if not (self.start_date and self.duration_days):
            raise ValidationError('Чтобы назначить бригаду, укажите дату начала работ и срок в днях.')
        orders, exceptions = self.crew.find_conflicts(self.start_date, self.end_date,
                                                      exclude_order=self)
        problems = [f'заказ №{o.pk} ({o.start_date:%d.%m.%Y}–{o.end_date:%d.%m.%Y})' for o in orders]
        problems += [f'{e.get_type_display().lower()} ({e.date_from:%d.%m.%Y}–{e.date_to:%d.%m.%Y})'
                     for e in exceptions]
        if problems:
            raise ValidationError(
                f'Бригада «{self.crew}» недоступна с {self.start_date:%d.%m.%Y} '
                f'по {self.end_date:%d.%m.%Y}: ' + '; '.join(problems) + '.')


class OrderItem(models.Model):
    """Состав заказа (связь «многие-ко-многим» заказ – услуга)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items',
                              verbose_name='Заказ')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='order_items',
                                verbose_name='Услуга')
    quantity = models.DecimalField('Количество', max_digits=10, decimal_places=2)
    unit_price = models.DecimalField('Цена за единицу', max_digits=10, decimal_places=2)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Состав заказа'
        constraints = [models.UniqueConstraint(fields=['order', 'service'], name='unique_order_service')]

    def __str__(self):
        return f'{self.service} × {self.quantity}'
