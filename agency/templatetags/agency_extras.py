"""Свои фильтры и теги шаблонов (подключаются через {% load agency_extras %})."""
from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def rub(value):
    """Фильтр: 12345.5 -> «12 346 ₽»; пустое значение -> «—»."""
    if value in (None, ''):
        return '—'
    return f"{number_format(round(value), use_l10n=True, force_grouping=True)} ₽"


@register.filter
def ru_plural(number, forms):
    """Фильтр: склонение по числу. {{ n|ru_plural:"услуга,услуги,услуг" }}."""
    one, few, many = forms.split(',')
    n = abs(int(number))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


@register.inclusion_tag('agency/tags/stat_card.html')
def stat_card(icon, value, label):
    """Тег: плитка со статистикой. {% stat_card 'bi-grid' 12 'услуг' %}."""
    return {'icon': icon, 'value': value, 'label': label}
