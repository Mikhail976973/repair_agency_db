from django.test import TestCase
from django.urls import reverse
from agency.models import Service, ServiceCategory, User, Order, OrderStatus, OrderItem


class ServiceCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = ServiceCategory.objects.create(name='Плитка')
        cls.free = Service.objects.create(category=cls.cat, name='Свободная услуга', price=100)
        cls.used = Service.objects.create(category=cls.cat, name='Заказанная услуга', price=200)
        st = OrderStatus.objects.create(name='Новый', sort_order=1)
        o = Order.objects.create(status=st, contact_name='Иван', contact_phone='+79990000000')
        OrderItem.objects.create(order=o, service=cls.used, quantity=2, unit_price=200)
        cls.client_u = User.objects.create_user('c', password='x', role='client')
        cls.manager = User.objects.create_user('m', password='x', role='manager')
        cls.admin_role = User.objects.create_user('a', password='x', role='admin')
        cls.su = User.objects.create_superuser('s', 's@x.ru', 'x')

    def urls(self):
        return [reverse('agency:service_create'),
                reverse('agency:service_edit', args=[self.free.pk]),
                reverse('agency:service_delete', args=[self.free.pk])]

    def test_guest_redirected_to_login(self):
        for u in self.urls():
            r = self.client.get(u)
            self.assertEqual(r.status_code, 302); self.assertIn('/accounts/login/', r['Location'])

    def test_client_forbidden(self):
        self.client.force_login(self.client_u)
        for u in self.urls():
            self.assertEqual(self.client.get(u).status_code, 403)
            self.assertEqual(self.client.post(u, {}).status_code, 403)
        self.assertTrue(Service.objects.filter(pk=self.free.pk).exists())

    def test_staff_roles_can_open(self):
        for user in (self.manager, self.admin_role, self.su):
            self.client.force_login(user)
            for u in self.urls():
                self.assertEqual(self.client.get(u).status_code, 200, (user, u))

    def test_create_edit_delete(self):
        self.client.force_login(self.manager)
        r = self.client.post(reverse('agency:service_create'),
                             {'category': self.cat.pk, 'name': 'Новая услуга', 'price': '500'})
        s = Service.objects.get(name='Новая услуга')
        self.assertRedirects(r, s.get_absolute_url()); self.assertEqual(s.updated_by, self.manager)
        r = self.client.post(reverse('agency:service_edit', args=[s.pk]),
                             {'category': self.cat.pk, 'name': 'Изменённая', 'price': '650'})
        s.refresh_from_db(); self.assertEqual((s.name, int(s.price)), ('Изменённая', 650))
        r = self.client.post(reverse('agency:service_delete', args=[s.pk]), follow=True)
        self.assertFalse(Service.objects.filter(pk=s.pk).exists())
        self.assertContains(r, 'удалена')
        # остальные остались
        self.assertTrue(Service.objects.filter(pk=self.free.pk).exists())

    def test_validation(self):
        self.client.force_login(self.manager)
        r = self.client.post(reverse('agency:service_create'),
                             {'category': self.cat.pk, 'name': 'ab', 'price': '-5'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'не короче трёх'); self.assertContains(r, 'больше нуля')

    def test_protected_delete_shows_message(self):
        self.client.force_login(self.su)
        r = self.client.post(reverse('agency:service_delete', args=[self.used.pk]), follow=True)
        self.assertTrue(Service.objects.filter(pk=self.used.pk).exists())
        self.assertContains(r, 'нельзя удалить')

    def test_buttons_visibility(self):
        edit = reverse('agency:service_edit', args=[self.free.pk])
        for user, visible in ((None, False), (self.client_u, False), (self.manager, True), (self.su, True)):
            self.client.logout()
            if user: self.client.force_login(user)
            for url in (reverse('agency:service_list'), self.free.get_absolute_url()):
                self.assertEqual(edit in self.client.get(url).content.decode(), visible, (user, url))
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.used.get_absolute_url()), 'Иван')
        self.client.force_login(self.client_u)
        self.assertNotContains(self.client.get(self.used.get_absolute_url()), 'Иван')
