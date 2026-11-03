from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class User(AbstractUser):
    """Клиенты и сотрудники (таблица users)."""

    class Role(models.TextChoices):
        CLIENT = 'client', 'Клиент'
        MANAGER = 'manager', 'Менеджер'
        ADMIN = 'admin', 'Администратор'

    phone = models.CharField('Телефон', max_length=20, blank=True)
    role = models.CharField('Роль', max_length=20, choices=Role.choices, default=Role.CLIENT)
    avatar = models.ImageField('Фото профиля', upload_to='avatars/', blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.get_full_name() or self.username


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
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT,
                               related_name='orders', verbose_name='Статус')
    contact_name = models.CharField('Имя контакта', max_length=100)
    contact_phone = models.CharField('Телефон контакта', max_length=20)
    total_cost = models.DecimalField('Стоимость', max_digits=12, decimal_places=2, default=0)
    services = models.ManyToManyField(Service, through='OrderItem', related_name='orders',
                                      verbose_name='Услуги')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Изменено', auto_now=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return f'Заказ №{self.pk} — {self.contact_name}'


class OrderItem(models.Model):
    """Состав заказа (связь «многие-ко-многим» заказ – услуга)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items',
                              verbose_name='Заказ')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='order_items',
                                verbose_name='Услуга')
    quantity = models.DecimalField('Количество', max_digits=10, decimal_places=2)
    unit_price = models.DecimalField('Цена за единицу', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Состав заказа'
        constraints = [models.UniqueConstraint(fields=['order', 'service'], name='unique_order_service')]

    def __str__(self):
        return f'{self.service} × {self.quantity}'
