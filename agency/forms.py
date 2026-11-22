from django import forms

from .models import Service, ServiceCategory
from .order_logic import MAX_SUBTOTAL, normalize_phone


class OrderRequestForm(forms.Form):
    """Заявка с главной страницы: контакты + количество по каждой услуге каталога."""

    contact_name = forms.CharField(label='Ваше имя', max_length=100)
    contact_phone = forms.CharField(label='Телефон', max_length=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.services = list(Service.objects.select_related('category')
                             .order_by('category__name', 'name'))
        for service in self.services:
            # по полю количества на каждую услугу: пусто или 0 = услуга не выбрана
            self.fields[f'qty_{service.pk}'] = forms.DecimalField(
                required=False, min_value=0, max_value=9999, decimal_places=2,
                error_messages={'min_value': 'Количество не может быть отрицательным.',
                                'max_value': 'Слишком большое количество.',
                                'invalid': 'Введите число.'})
        self.items = []

    def grouped(self):
        """[(название категории, [(услуга, поле количества), ...]), ...] для шаблона."""
        groups = {}
        for service in self.services:
            groups.setdefault(service.category.name, []).append(
                (service, self[f'qty_{service.pk}']))
        return list(groups.items())

    def clean_contact_name(self):
        name = ' '.join(self.cleaned_data['contact_name'].split())
        if len(name) < 2:
            raise forms.ValidationError('Укажите имя.')
        return name

    def clean_contact_phone(self):
        return normalize_phone(self.cleaned_data['contact_phone'])

    def clean(self):
        cleaned = super().clean()
        if any(name.startswith('qty_') for name in self.errors):
            return cleaned          # ошибки в количествах уже показаны у полей
        self.items = [(s, cleaned[f'qty_{s.pk}']) for s in self.services
                      if cleaned.get(f'qty_{s.pk}')]
        if not self.items:
            raise forms.ValidationError('Выберите хотя бы одну услугу и укажите количество.')
        if sum(s.price * q for s, q in self.items) > MAX_SUBTOTAL:
            raise forms.ValidationError('Слишком большая сумма заявки: уточните объёмы работ.')
        return cleaned


class ServiceForm(forms.ModelForm):
    """Добавление и редактирование услуги (для менеджера и администратора)."""

    class Meta:
        model = Service
        fields = ['category', 'name', 'price', 'image']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например, Укладка плитки'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {'price': 'Цена за единицу, ₽'}

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if len(name) < 3:
            raise forms.ValidationError('Название должно быть не короче трёх символов.')
        return name

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError('Цена должна быть больше нуля.')
        return price
