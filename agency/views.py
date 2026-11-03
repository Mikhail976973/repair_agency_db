from django.shortcuts import get_object_or_404, render

from .models import Service, ServiceCategory


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
