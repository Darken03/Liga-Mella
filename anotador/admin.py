from django.contrib import admin
from .models import Sustitucion


@admin.register(Sustitucion)
class SustitucionAdmin(admin.ModelAdmin):
    list_display = ('juego', 'equipo', 'tipo', 'sale', 'entra', 'orden_sale', 'orden_entra', 'creada')
    list_filter = ('tipo', 'equipo')
