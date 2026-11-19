from django.db.models import (Avg, Case, CharField, Count, DecimalField,
                              ExpressionWrapper, F, Max, Min, Q, Sum, Value, When)
from django.shortcuts import get_object_or_404, render

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


def dashboard(request):
    user = request.user
    context = {'catalog': catalog_widget()}
    if user.is_authenticated:
        context['orders'] = orders_widget(user)
        context['is_staff_member'] = is_staff_member(user)
    if user.is_superuser:
        context['management'] = management_widget()
    return render(request, 'agency/dashboard.html', context)


# ---------- Каталог ----------

def service_list(request):
    category_id = request.GET.get('category')
    services = Service.objects.select_related('category')
    if category_id:
        services = services.filter(category_id=category_id)
    return render(request, 'agency/service_list.html', {
        'services': services,
        'categories': ServiceCategory.objects.all(),
        'current_category': category_id,
    })


def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)
    return render(request, 'agency/service_detail.html', {'service': service})
