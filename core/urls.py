from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('noticias/', views.noticias, name='noticias'),
    path('noticias/<int:pk>/', views.noticia_detalle, name='noticia_detalle'),
    path('juegos/', views.juegos, name='juegos'),
    path('juegos/<int:pk>/', views.juego_detalle, name='juego_detalle'),
    path('posiciones/', views.posiciones, name='posiciones'),
    path('playoffs/', views.playoffs, name='playoffs'),
    path('reglas/', views.reglas, name='reglas'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('equipos/', views.equipos_list, name='equipos'),
    path('equipos/<int:pk>/', views.equipo_detalle, name='equipo_detalle'),
    path('jugadores/<int:pk>/', views.jugador_detalle, name='jugador_detalle'),
    path('ui-kit/', views.ui_kit, name='ui_kit'),
]
