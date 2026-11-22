from functools import wraps

from django.db.models import (Avg, Case, CharField, Count, DecimalField,
                              ExpressionWrapper, F, Max, Min, Q, Sum, Value, When)
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import OrderRequestForm, ServiceForm
from .order_logic import DISCOUNT_STEPS, create_order_request
from .templatetags.agency_extras import rub
from .models import (FINISHED_STATUSES, Crew, Order, OrderItem, OrderStatus, Service,
                     ServiceCategory, User)

MONEY = DecimalField(max_digits=14, decimal_places=2)


def is_staff_member(user):
    """Менеджер, администратор по роли или суперпользователь."""
    return user.is_authenticated and (
        user.is_superuser or user.role in (User.Role.MANAGER, User.Role.ADMIN))


# ---------- Виджет 1: каталог услуг (виден всем) ----------

def catalog_widget():
    """Таблицы: Service, ServiceCategory, OrderItem, Order (через статус заказа)."""
    line_sum = ExpressionWrapper(F('order_items__quantity') * F('order_items__unit_price'),
                                 output_field=MONEY)
    not_cancelled = ~Q(order_items__order__status__name='Отменён')

    # annotate: у каждой услуги считаем число заказов и выручку (отменённые не в счёт)
    top_services = (Service.objects.select_related('category')
                    .annotate(orders_count=Count('order_items__order', filter=not_cancelled,
                                                 distinct=True),
                              revenue=Sum(line_sum, filter=not_cancelled))
                    .filter(orders_count__gt=0)
                    .order_by('-revenue')[:5])

    # annotate по категориям: сколько услуг и какая средняя цена
    categories = (ServiceCategory.objects
                  .annotate(services_count=Count('services'), avg_price=Avg('services__price'))
                  .order_by('-services_count', 'name'))

    # aggregate: одна строка итогов по всему каталогу
    catalog_stats = Service.objects.aggregate(
        total=Count('id'), min_price=Min('price'), max_price=Max('price'), avg_price=Avg('price'))

    return {'top_services': top_services, 'categories': categories,
            'catalog_stats': catalog_stats}


# ---------- Виджет 2: заказы (для вошедших) ----------

def orders_widget(user):
    """Таблицы: Order, OrderStatus, User, Crew. Клиент видит только свои заказы."""
    orders = Order.objects.select_related('status', 'crew', 'client')
    if not is_staff_member(user):
        orders = orders.filter(client=user)

    summary = orders.exclude(status__name='Отменён').aggregate(
        count=Count('id'), total=Sum('total_cost'), avg=Avg('total_cost'))

    by_status = (orders.values('status__name', 'status__sort_order')
                 .annotate(count=Count('id'), total=Sum('total_cost'))
                 .order_by('status__sort_order'))

    active = (orders.exclude(status__name__in=FINISHED_STATUSES)
              .annotate(size=Case(
                  When(total_cost__gte=100000, then=Value('крупный')),
                  When(total_cost__gte=30000, then=Value('средний')),
                  default=Value('малый'), output_field=CharField()))
              .order_by('start_date')[:6])

    return {'summary': summary, 'by_status': by_status, 'active': active}


# ---------- Виджет 3: бригады и финансы (только суперпользователь) ----------

def management_widget():
    """Таблицы: Crew, CrewScheduleException, Order, User."""
    unfinished = ~Q(orders__status__name__in=FINISHED_STATUSES)
    crews = (Crew.objects.select_related('foreman')
             .annotate(active_orders=Count('orders', filter=unfinished, distinct=True),
                       done_orders=Count('orders', filter=Q(orders__status__name='Сдан'),
                                         distinct=True),
                       off_periods=Count('exceptions', distinct=True))
             .order_by('-active_orders', 'name'))

    finance = Order.objects.exclude(status__name='Отменён').aggregate(
        revenue=Sum('total_cost'), avg=Avg('total_cost'), biggest=Max('total_cost'),
        orders=Count('id'), big_orders=Count('id', filter=Q(total_cost__gte=100000)))

    managers = (User.objects.filter(role=User.Role.MANAGER)
                .annotate(orders_count=Count('managed_orders'),
                          orders_sum=Sum('managed_orders__total_cost'))
                .order_by('-orders_sum'))

    unassigned = (Order.objects.filter(crew__isnull=True)
                  .exclude(status__name__in=FINISHED_STATUSES).count())

    return {'crews': crews, 'finance': finance, 'managers': managers,
            'unassigned': unassigned}


def charts_data(user):
    """Данные для графиков (Chart.js): передаются в шаблон через json_script."""
    # число заказов по категориям услуг (отменённые не считаем)
    categories = (ServiceCategory.objects
                  .annotate(orders_count=Count(
                      'services__order_items__order',
                      filter=~Q(services__order_items__order__status__name='Отменён'),
                      distinct=True))
                  .order_by('-orders_count', 'name'))
    return {'categories': {'labels': [c.name for c in categories],
                           'values': [c.orders_count for c in categories]}}


def order_request(request):
    """Обработка формы заявки: возвращает (форма, ответ-редирект или None)."""
    user = request.user
    if request.method != 'POST':
        initial = {}
        if user.is_authenticated:
            initial = {'contact_name': user.get_full_name() or user.username,
                       'contact_phone': user.phone}
        return OrderRequestForm(initial=initial), None

    form = OrderRequestForm(request.POST)
    if not form.is_valid():
        return form, None
    order, percent = create_order_request(
        name=form.cleaned_data['contact_name'], phone=form.cleaned_data['contact_phone'],
        items=form.items, client=user if user.is_authenticated else None)
    text = (f'Заявка №{order.pk} принята. Позиций: {order.items.count()}, '
            f'сумма {rub(order.total_cost)}')
    if percent:
        text += f' (скидка {percent}%)'
    text += (f'. Менеджер {order.manager} свяжется с вами по телефону {order.contact_phone}.'
             if order.manager else '. Менеджер свяжется с вами по указанному телефону.')
    messages.success(request, text)
    return form, redirect(f"{reverse('agency:dashboard')}#order")


def dashboard(request):
    user = request.user
    order_form, response = order_request(request)
    if response:
        return response
    context = {'catalog': catalog_widget(), 'charts': charts_data(user),
               'order_form': order_form,
               'discount_steps': [{'threshold': t, 'percent': p} for t, p in DISCOUNT_STEPS]}
    if user.is_authenticated:
        orders = orders_widget(user)
        orders['by_status'] = list(orders['by_status'])
        context['orders'] = orders
        context['is_staff_member'] = is_staff_member(user)
        context['charts']['statuses'] = {
            'labels': [r['status__name'] for r in orders['by_status']],
            'values': [r['count'] for r in orders['by_status']]}
    if user.is_superuser:
        context['management'] = management_widget()
    return render(request, 'agency/dashboard.html', context)


# ---------- Каталог ----------

def search_filter(query, *fields):
    """Поиск без учёта регистра. В SQLite LIKE не различает регистр только у латиницы,
    поэтому для кириллицы перебираем несколько вариантов написания."""
    variants = {query, query.lower(), query.upper(), query.capitalize()}
    condition = Q()
    for field in fields:
        for variant in variants:
            condition |= Q(**{f'{field}__icontains': variant})
    return condition


def service_list(request):
    category_id = request.GET.get('category')
    query = request.GET.get('q', '').strip()
    services = Service.objects.select_related('category')
    if category_id:
        services = services.filter(category_id=category_id)
    if query:
        services = services.filter(search_filter(query, 'name', 'category__name'))
    return render(request, 'agency/service_list.html', {
        'can_manage': is_staff_member(request.user),
        'services': services,
        'categories': ServiceCategory.objects.all(),
        'current_category': category_id,
        'q': query,
    })


def service_detail(request, pk):
    service = get_object_or_404(Service.objects.select_related('category'), pk=pk)
    orders_count = (service.order_items.exclude(order__status__name='Отменён')
                    .values('order').distinct().count())
    related = Service.objects.filter(category=service.category).exclude(pk=service.pk)[:3]
    # связанная таблица: позиции заказов с этой услугой (новые заказы сверху)
    order_items = (service.order_items.select_related('order__status')
                   .order_by('-order__created_at')[:10])
    return render(request, 'agency/service_detail.html', {
        'service': service, 'orders_count': orders_count, 'related': related,
        'order_items': order_items, 'can_manage': is_staff_member(request.user)})


# ---------- Управление услугами (менеджер, администратор, суперпользователь) ----------

def staff_only(view):
    """Гостя отправляет на вход, вошедшего без прав (клиента) — на страницу 403."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_staff_member(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


@staff_only
def service_create(request):
    form = ServiceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        service = form.save(commit=False)
        service.updated_by = request.user
        service.save()
        messages.success(request, f'Услуга «{service.name}» добавлена')
        return redirect(service)
    return render(request, 'agency/service_form.html', {'form': form, 'service': None})


@staff_only
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, request.FILES or None, instance=service)
    if request.method == 'POST' and form.is_valid():
        service = form.save(commit=False)
        service.updated_by = request.user
        service.save()
        messages.success(request, f'Изменения в услуге «{service.name}» сохранены')
        return redirect(service)
    return render(request, 'agency/service_form.html', {'form': form, 'service': service})


@staff_only
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        name = service.name
        try:
            service.delete()
        except ProtectedError:
            # услуга есть в заказах (OrderItem.service on_delete=PROTECT)
            messages.error(request, f'Услугу «{name}» нельзя удалить: она есть в заказах. '
                                    'Измените её или оставьте в каталоге.')
            return redirect(service)
        messages.success(request, f'Услуга «{name}» удалена')
        return redirect('agency:service_list')
    orders_count = service.order_items.values('order').distinct().count()
    return render(request, 'agency/service_confirm_delete.html',
                  {'service': service, 'orders_count': orders_count})
