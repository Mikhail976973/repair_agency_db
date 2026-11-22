"""Бизнес-логика заявки с сайта: расчёт скидки, выбор менеджера, создание заказа."""
import re
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q

from .models import FINISHED_STATUSES, Order, OrderItem, OrderStatus, User

# Скидка зависит от суммы заявки: (порог суммы в рублях, скидка в %), от большего к меньшему
DISCOUNT_STEPS = ((300000, 10), (100000, 5))
NEW_ORDER_STATUS = 'Заявка'
MAX_SUBTOTAL = Decimal('100000000')
CENT = Decimal('0.01')


def normalize_phone(raw):
    """«8 (900) 123-45-67», «+7 900 123 45 67», «9001234567» -> «+79001234567»."""
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 11 and digits[0] in '78':
        digits = digits[1:]
    if len(digits) != 10:
        raise ValidationError('Введите телефон в формате +7 900 123-45-67.')
    return '+7' + digits


def discount_percent(subtotal):
    """Скидка в процентах для суммы заявки до скидки."""
    for threshold, percent in DISCOUNT_STEPS:
        if subtotal >= threshold:
            return percent
    return 0


def pick_manager():
    """Менеджер с наименьшим числом незавершённых заказов (при равенстве — по id)."""
    return (User.objects.filter(role=User.Role.MANAGER)
            .annotate(active=Count('managed_orders',
                                   filter=~Q(managed_orders__status__name__in=FINISHED_STATUSES)))
            .order_by('active', 'pk').first())


@transaction.atomic
def create_order_request(*, name, phone, items, client=None):
    """Создаёт заказ в статусе «Заявка» из списка [(Service, количество)].

    Цены берутся из БД, а не из формы: так их нельзя подменить в браузере.
    Скидка записывается в цену позиции (unit_price), а итог считается так же, как в админке.
    """
    subtotal = sum((service.price * qty for service, qty in items), Decimal('0'))
    percent = discount_percent(subtotal)
    status, _ = OrderStatus.objects.get_or_create(name=NEW_ORDER_STATUS,
                                                  defaults={'sort_order': 0})
    order = Order.objects.create(client=client, manager=pick_manager(), status=status,
                                 contact_name=name, contact_phone=phone)
    total = Decimal('0')
    for service, qty in items:
        unit_price = (service.price * (100 - percent) / 100).quantize(CENT, ROUND_HALF_UP)
        OrderItem.objects.create(order=order, service=service, quantity=qty,
                                 unit_price=unit_price)
        total += qty * unit_price
    order.total_cost = total.quantize(CENT, ROUND_HALF_UP)
    order.save(update_fields=['total_cost', 'updated_at'])
    return order, percent
