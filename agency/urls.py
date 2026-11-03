from django.urls import path

from . import views

app_name = 'agency'

urlpatterns = [
    path('', views.service_list, name='service_list'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
]
