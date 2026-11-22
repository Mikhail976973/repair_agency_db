import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from agency.models import Order, OrderItem, OrderStatus, Service, User


class Command(BaseCommand):
    help = 'Добавляет случайных клиентов и заказы через Faker'

    def add_arguments(self, parser):
        parser.add_argument('--clients', type=int, default=10)
        parser.add_argument('--orders', type=int, default=20)

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker('ru_RU')
        services = list(Service.objects.all())
        statuses = list(OrderStatus.objects.all())
        managers = list(User.objects.filter(role=User.Role.MANAGER))

        clients = []
        for _ in range(options['clients']):
            male = random.random() < 0.5          # имя и фамилия одного пола
            clients.append(User.objects.create_user(
                username=fake.unique.user_name(),
                password='demo12345',
                first_name=fake.first_name_male() if male else fake.first_name_female(),
                last_name=fake.last_name_male() if male else fake.last_name_female(),
                email=fake.email(),
                phone=fake.phone_number()[:20],
                role=User.Role.CLIENT))

        for _ in range(options['orders']):
            client = random.choice(clients or list(User.objects.filter(role=User.Role.CLIENT)))
            order = Order.objects.create(
                client=client,
                manager=random.choice(managers) if managers else None,
                status=random.choice(statuses),
                contact_name=client.get_full_name(),
                contact_phone=client.phone)
            total = Decimal('0')
            for service in random.sample(services, random.randint(1, 4)):
                quantity = Decimal(random.randint(1, 50))
                OrderItem.objects.create(order=order, service=service,
                                         quantity=quantity, unit_price=service.price)
                total += quantity * service.price
            Order.objects.filter(pk=order.pk).update(
                total_cost=total,
                created_at=timezone.now() - timedelta(days=random.randint(0, 120)))

        self.stdout.write(self.style.SUCCESS(
            f'Создано клиентов: {options["clients"]}, заказов: {options["orders"]}'))
