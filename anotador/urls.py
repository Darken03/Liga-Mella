from django.urls import path
from . import views
urlpatterns = [
    path('', views.lista, name='anotador_lista'),
    path('juego/<int:pk>/', views.anotar, name='anotar_juego'),
    path('juego/<int:pk>/api/estado/', views.api_estado, name='anotar_api_estado'),
    path('juego/<int:pk>/api/turno/', views.api_turno, name='anotar_api_turno'),
    path('juego/<int:pk>/api/control/', views.api_control, name='anotar_api_control'),
    path('juego/<int:pk>/api/deshacer/', views.api_deshacer, name='anotar_api_deshacer'),
    path('juego/<int:pk>/api/pitcher/', views.api_pitcher, name='anotar_api_pitcher'),
]
