from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('core.urls')),
    path('cuenta/', include('usuarios.urls')),
    path('cuenta/', include('notificaciones.urls')),
    path('admin-liga/', include('administracion.urls')),
    path('capitan/', include('capitanes.urls')),
    path('anotador/', include('anotador.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
