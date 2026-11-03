from django.core.management.base import BaseCommand

from agency.models import OrderStatus, Service, ServiceCategory


class Command(BaseCommand):
    help = 'Заполняет справочники и каталог услуг демонстрационными данными'

    def handle(self, *args, **options):
        for i, name in enumerate(['Заявка', 'Согласование', 'Демонтаж', 'Черновые работы',
                                  'Чистовая отделка', 'Сдан']):
            OrderStatus.objects.get_or_create(name=name, defaults={'sort_order': i})
        data = {
            'Демонтаж': [('Демонтаж стен', 450), ('Демонтаж пола', 300)],
            'Электрика': [('Замена проводки', 900), ('Установка розеток', 350)],
            'Отделка': [('Поклейка обоев', 400), ('Покраска стен', 380)],
        }
        for cat, items in data.items():
            c, _ = ServiceCategory.objects.get_or_create(name=cat)
            for name, price in items:
                Service.objects.get_or_create(category=c, name=name, defaults={'price': price})
        self.stdout.write(self.style.SUCCESS('Демо-данные добавлены'))
