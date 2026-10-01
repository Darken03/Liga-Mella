from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='cap_dash'),
    path('mis-estadisticas/', views.mis_stats, name='cap_mis_stats'),
    path('mi-equipo/', views.perfil_equipo, name='cap_perfil'),
    # Jugadores
    path('jugadores/', views.jugadores, name='cap_jugadores'),
    path('jugadores/<int:pk>/', views.jugador_detalle, name='cap_jugador_detalle'),
    path('jugadores/<int:pk>/expulsar/', views.jugador_expulsar, name='cap_jugador_expulsar'),
    # Juegos
    path('juegos/', views.juegos, name='cap_juegos'),
    path('juegos/<int:pk>/', views.juego_detalle, name='cap_juego_detalle'),
    # Fichajes
    path('fichajes/', views.fichajes, name='cap_fichajes'),
    path('solicitar/', views.solicitar, name='cap_solicitar'),
    path('fichajes/<int:pk>/aprobar/', views.fichaje_aprobar, name='cap_fichaje_aprobar'),
    path('fichajes/<int:pk>/rechazar/', views.fichaje_rechazar, name='cap_fichaje_rechazar'),
    path('fichajes/<int:pk>/cancelar/', views.fichaje_cancelar, name='cap_fichaje_cancelar'),
    path('cambiar-estado/', views.cambiar_estado, name='cap_cambiar_estado'),
    # Alineaciones
    path('alineaciones/', views.alineaciones, name='cap_alineaciones'),
    path('alineaciones/juego/<int:juego_id>/', views.alineacion_editar, name='cap_alin_editar'),
    path('alineaciones/plantilla/<int:pk>/eliminar/', views.plantilla_eliminar, name='cap_plantilla_eliminar'),
    # Titular regular (página pública)
    path('titular/', views.titular, name='cap_titular'),
]
