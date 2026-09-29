from django.contrib import admin
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'titulo', 'leida', 'creada')
    list_filter = ('tipo', 'leida')
    search_fields = ('usuario__username', 'titulo', 'mensaje')
