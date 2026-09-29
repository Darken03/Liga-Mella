from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import MellaLogin, redirigir, mi_perfil, configurar, mis_solicitudes, solicitud_detalle, solicitud_aceptar, solicitud_rechazar, registro
urlpatterns = [path('login/', MellaLogin.as_view(), name='login'), path('registro/', registro, name='registro'), path('logout/', LogoutView.as_view(), name='logout'), path('redirigir/', redirigir, name='redirigir'),
    path('perfil/', mi_perfil, name='mi_perfil'),
    path('configurar/', configurar, name='configurar'),
    path('solicitudes/', mis_solicitudes, name='mis_solicitudes'),
    path('solicitudes/<int:pk>/', solicitud_detalle, name='sol_detalle'),
    path('solicitudes/<int:pk>/aceptar/', solicitud_aceptar, name='sol_aceptar'),
    path('solicitudes/<int:pk>/rechazar/', solicitud_rechazar, name='sol_rechazar')]
