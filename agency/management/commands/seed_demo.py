import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from agency.models import (Crew, CrewScheduleException, Order, OrderItem, OrderStatus,
                           Service, ServiceCategory, User)

STATUSES = ['Заявка', 'Замер', 'Согласование', 'Закупка материалов', 'Демонтаж',
            'Черновые работы', 'Чистовая отделка', 'Приёмка', 'Сдан', 'Отменён']

CATALOG = {
    'Демонтаж': [('Демонтаж стен', 450), ('Демонтаж пола', 300)],
    'Электрика': [('Замена проводки', 900), ('Установка розеток', 350)],
    'Отделка': [('Поклейка обоев', 400), ('Покраска стен', 380)],
    'Сантехника': [('Замена труб', 1200), ('Установка ванны', 5500)],
    'Полы': [('Укладка ламината', 650), ('Стяжка пола', 700)],
    'Потолки': [('Натяжной потолок', 850), ('Гипсокартонный потолок', 1300)],
    'Окна и двери': [('Установка окна', 6500), ('Установка межкомнатной двери', 3200)],
    'Плитка': [('Укладка плитки', 1100), ('Затирка швов', 250)],
    'Штукатурка': [('Штукатурка стен', 550), ('Шпаклёвка стен', 420)],
    'Утепление': [('Утепление стен', 780), ('Утепление балкона', 2400)],
}

CREWS = ['Бригада Иванова', 'Электрики', 'Сантехники', 'Плиточники', 'Маляры',
         'Штукатуры', 'Монтажники окон', 'Универсалы', 'Бригада Петрова', 'Кровельщики']

PEOPLE = [
    # username, имя, фамилия, роль, номер бригады (для мастеров)
    ('manager1', 'Анна', 'Смирнова', User.Role.MANAGER, None),
    ('manager2', 'Игорь', 'Козлов', User.Role.MANAGER, None),
    ('worker1', 'Пётр', 'Иванов', User.Role.WORKER, 0),
    ('worker2', 'Сергей', 'Электров', User.Role.WORKER, 1),
    ('worker3', 'Олег', 'Трубин', User.Role.WORKER, 2),
    ('worker4', 'Максим', 'Плиткин', User.Role.WORKER, 3),
    ('client1', 'Мария', 'Орлова', User.Role.CLIENT, None),
    ('client2', 'Дмитрий', 'Волков', User.Role.CLIENT, None),
    ('client3', 'Елена', 'Новикова', User.Role.CLIENT, None),
    ('client4', 'Андрей', 'Морозов', User.Role.CLIENT, None),
    ('client5', 'Ольга', 'Лебедева', User.Role.CLIENT, None),
]

# Этапы 10 заказов в работе и 4 завершённых
ACTIVE = ['Заявка', 'Замер', 'Согласование', 'Закупка материалов', 'Демонтаж',
          'Черновые работы', 'Чистовая отделка', 'Приёмка', 'Демонтаж', 'Черновые работы']
FINISHED = ['Сдан', 'Сдан', 'Сдан', 'Отменён']
PASSWORD = 'demo12345'


class Command(BaseCommand):
    help = 'Заполняет все таблицы демонстрационными данными (не менее 10 записей в каждой)'

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(7)
        today = timezone.localdate()

        statuses = {}
        for i, name in enumerate(STATUSES):
            statuses[name], _ = OrderStatus.objects.update_or_create(
                name=name, defaults={'sort_order': i})

        services = []
        for cat_name, items in CATALOG.items():
            cat, _ = ServiceCategory.objects.get_or_create(name=cat_name)
            for name, price in items:
                s, _ = Service.objects.get_or_create(category=cat, name=name,
                                                     defaults={'price': price})
                services.append(s)

        crews = [Crew.objects.get_or_create(name=n)[0] for n in CREWS]

        admin, created = User.objects.get_or_create(
            username='admin', defaults={'is_superuser': True, 'is_staff': True,
                                        'role': User.Role.ADMIN, 'first_name': 'Админ',
                                        'last_name': 'Агентства', 'email': 'admin@example.com'})
        if created:
            admin.set_password(PASSWORD)
            admin.save()

        users = {}
        for username, first, last, role, crew_idx in PEOPLE:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last, 'role': role,
                          'email': f'{username}@example.com',
                          'phone': f'+7900{rng.randint(1000000, 9999999)}',
                          'crew': crews[crew_idx] if crew_idx is not None else None})
            if created:
                u.set_password(PASSWORD)
                u.save()
            users[username] = u
        for i, w in enumerate(['worker1', 'worker2', 'worker3', 'worker4']):
            crews[i].foreman = users[w]
            crews[i].save()

        types = list(CrewScheduleException.Type.values)
        for i, crew in enumerate(crews):
            start = today + timedelta(days=40 + i * 6)
            CrewScheduleException.objects.get_or_create(
                crew=crew, note=f'Демо-период {i + 1}',
                defaults={'type': types[i % 3], 'date_from': start,
                          'date_to': start + timedelta(days=3)})

        if Order.objects.count() < 14:
            self.make_orders(rng, today, statuses, services, crews, users)

        self.stdout.write(self.style.SUCCESS(
            f'Готово. Пароль всех демо-пользователей и admin: {PASSWORD}'))

    def make_orders(self, rng, today, statuses, services, crews, users):
        clients = [users[f'client{i}'] for i in range(1, 6)]
        managers = [users['manager1'], users['manager2']]
        plan = [(s, False) for s in ACTIVE] + [(s, True) for s in FINISHED]
        for i, (status_name, finished) in enumerate(plan):
            if finished:
                start = today - timedelta(days=150 - i * 15)
                duration = rng.randint(10, 25)
            else:
                start = today + timedelta(days=-8 + i * 3)
                duration = rng.randint(5, 12)
            no_crew = status_name in ('Заявка', 'Замер')
            order = Order.objects.create(
                client=None if i == 5 else clients[i % len(clients)],
                manager=managers[i % 2],
                crew=None if no_crew else crews[i % len(crews)],
                status=statuses[status_name],
                contact_name=f'Контакт {i + 1}',
                contact_phone=f'+7911{rng.randint(1000000, 9999999)}',
                start_date=None if no_crew else start,
                duration_days=None if no_crew else duration)
            total = Decimal('0')
            for s in rng.sample(services, rng.randint(2, 4)):
                qty = Decimal(rng.randint(5, 60))
                price = s.price
                if rng.random() < 0.3:
                    price = (price * Decimal('0.9')).quantize(Decimal('0.01'))
                OrderItem.objects.create(order=order, service=s, quantity=qty, unit_price=price)
                total += qty * price
            Order.objects.filter(pk=order.pk).update(
                total_cost=total,
                created_at=timezone.now() - timedelta(days=(150 if finished else 20) - i * 4))
