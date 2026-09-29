from django.contrib import admin
from .models import Alineacion, AlineacionDetalle, PlantillaAlineacion, PlantillaDetalle


class AlineacionDetalleInline(admin.TabularInline):
    model = AlineacionDetalle
    extra = 0


@admin.register(Alineacion)
class AlineacionAdmin(admin.ModelAdmin):
    list_display = ('equipo', 'juego', 'actualizada')
    inlines = [AlineacionDetalleInline]


class PlantillaDetalleInline(admin.TabularInline):
    model = PlantillaDetalle
    extra = 0


@admin.register(PlantillaAlineacion)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ('equipo', 'nombre', 'creada')
    inlines = [PlantillaDetalleInline]
