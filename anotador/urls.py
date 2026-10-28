from django.urls import path
from . import views
urlpatterns = [
    path('', views.lista, name='anotador_lista'),
    path('juego/<int:pk>/', views.anotar, name='anotar_juego'),
    path('juego/<int:pk>/api/estado/', views.api_estado, name='anotar_api_estado'),
    path('juego/<int:pk>/api/turno/', views.api_turno, name='anotar_api_turno'),
    path('juego/<int:pk>/api/control/', views.api_control, name='anotar_api_control'),
    path('juego/<int:pk>/api/deshacer/', views.api_deshacer, name='anotar_api_deshacer'),
    path('juego/<int:pk>/api/cambio/', views.api_cambio, name='anotar_api_cambio'),
    path('juego/<int:pk>/api/pitcher/', views.api_pitcher, name='anotar_api_pitcher'),
    # Modo rápido: estadísticas sin alineación (marcador manual)
    path('juego/<int:pk>/rapido/', views.anotar_rapido, name='anotar_juego_rapido'),
    path('juego/<int:pk>/api/rapido/estado/', views.api_rapido_estado, name='anotar_api_rapido_estado'),
    path('juego/<int:pk>/api/rapido/turno/', views.api_rapido_turno, name='anotar_api_rapido_turno'),
    path('juego/<int:pk>/api/rapido/deshacer/', views.api_rapido_deshacer, name='anotar_api_rapido_deshacer'),
    path('juego/<int:pk>/api/rapido/puntuar/', views.api_rapido_puntuar, name='anotar_api_rapido_puntuar'),
    path('juego/<int:pk>/api/rapido/control/', views.api_rapido_control, name='anotar_api_rapido_control'),
]
