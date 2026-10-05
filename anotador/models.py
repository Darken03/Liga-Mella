from django.db import models


class Sustitucion(models.Model):
    """Auditoría de cambios del anotador: sustituciones y swaps defensivos.

    Guarda lo necesario para mostrar el historial y para revertir
    con Deshacer sin tocar las stats de bateo/pitcheo.
    """
    TIPOS = [('sustitucion', 'Sustitución'), ('swap_pos', 'Swap defensivo')]
    juego = models.ForeignKey('torneos.Juego', on_delete=models.CASCADE, related_name='cambios')
    equipo = models.ForeignKey('equipos.Equipo', on_delete=models.CASCADE, related_name='cambios')
    jugada = models.OneToOneField('torneos.Jugada', null=True, blank=True,
                                  on_delete=models.CASCADE, related_name='sustitucion')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='sustitucion')
    # sustitución banca: sale estaba en orden_sale, entra no estaba
    # sustitución swap: sale y entra estaban en orden_sale / orden_entra y se intercambian
    sale = models.ForeignKey('equipos.Jugador', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='cambios_salida')
    entra = models.ForeignKey('equipos.Jugador', null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='cambios_entrada')
    orden_sale = models.PositiveIntegerField(null=True, blank=True)
    orden_entra = models.PositiveIntegerField(null=True, blank=True)
    pos_sale_old = models.CharField(max_length=5, blank=True, default='')
    pos_sale_new = models.CharField(max_length=5, blank=True, default='')
    pos_entra_old = models.CharField(max_length=5, blank=True, default='')
    pos_entra_new = models.CharField(max_length=5, blank=True, default='')
    inning_num = models.PositiveIntegerField(default=1)
    mitad = models.CharField(max_length=10, default='alta')
    s_idx = models.PositiveIntegerField(default=0)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        if self.tipo == 'swap_pos':
            return f"Swap {self.sale} ({self.pos_sale_old}->{self.pos_sale_new}) x {self.entra} en {self.juego}"
        return f"Cambio {self.sale} -> {self.entra} (orden {self.orden_sale}) en {self.juego}"
