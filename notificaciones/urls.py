from django.urls import path
from . import views

urlpatterns = [
    path('notificaciones/', views.lista, name='notif_lista'),
    path('notificaciones/<int:pk>/ir/', views.leer_y_ir, name='notif_ir'),
    path('notificaciones/leer-todas/', views.marcar_todas, name='notif_leer_todas'),
    path('notificaciones/api/no-leidas/', views.api_no_leidas, name='notif_api'),
]
