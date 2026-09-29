from django.db import models
from django.conf import settings
from equipos.models import Equipo, Jugador, POSICIONES
from torneos.models import Juego


class Alineacion(models.Model):
    """Alineación de un equipo para un juego concreto: posiciones + orden al bate."""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='alineaciones')
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='alineaciones')
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notas = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('equipo', 'juego')]
        ordering = ['-actualizada']

    def __str__(self):
        return f"{self.equipo} vs {self.juego} ({self.detalles.count()} jug.)"

    def orden_bateo(self):
        return self.detalles.select_related('jugador').order_by('orden_bateo')

    def tiene_jugadores(self):
        return self.detalles.exists()


def get_alineacion_efectiva(juego, equipo):
    """Devuelve (alineacion, prestada, juego_origen) para mostrar en detalles.

    - Primero busca la alineación propia del juego con al menos 1 jugador.
    - Si no hay, busca la del juego pareja ida/vuelta del MISMO DÍA
      (mismos dos equipos, local/visita invertidos) — caso doble cartelera
      como B-Dbacks vs Clásicos (290 ida / 293 vuelta).
    - Las vacías (0 detalles, creadas al abrir el editor) se ignoran.
    """
    directa = (Alineacion.objects
               .filter(juego=juego, equipo=equipo)
               .prefetch_related('detalles__jugador').first())
    if directa is not None and directa.detalles.exists():
        return directa, False, juego
    try:
        from django.utils import timezone as _tz
        from django.db.models import Q as _Q
        from torneos.models import Juego as _Juego
        dia = _tz.localtime(juego.fecha).date()
        parejas = list(_Juego.objects.filter(fecha__date=dia).filter(
            _Q(local=juego.local, visita=juego.visita)
            | _Q(local=juego.visita, visita=juego.local)
        ).exclude(pk=juego.pk).order_by('fecha'))
        for pj in parejas:
            cand = (Alineacion.objects
                    .filter(juego=pj, equipo=equipo)
                    .prefetch_related('detalles__jugador').first())
            if cand is not None and cand.detalles.exists():
                return cand, True, pj
    except Exception:
        pass
    return None, False, None


def mapa_efectivo_juegos(juegos_dia):
    """{(juego_id, equipo_id): (n, prestada)} con fallback a la pareja ida/vuelta.

    Para que en la cartelera el juego 290 (ida) muestre la alineación
    guardada solo en el 293 (vuelta) del mismo día.
    """
    from django.db.models import Count as _Count
    directa = {}
    try:
        conteo = (Alineacion.objects.filter(juego__in=juegos_dia)
                  .values('juego_id', 'equipo_id').annotate(n=_Count('detalles')))
        directa = {(c['juego_id'], c['equipo_id']): c['n'] for c in conteo}
    except Exception:
        directa = {}
    # agrupar por pareja del día: mismos dos equipos
    grupos = {}
    for j in juegos_dia:
        key = tuple(sorted((j.local_id, j.visita_id)))
        grupos.setdefault(key, []).append(j)
    # mejor conteo por equipo dentro de cada pareja
    mejor_por_grupo = {}
    for key, lista in grupos.items():
        mejor = {}
        for j in lista:
            for eq_id in (j.local_id, j.visita_id):
                n = directa.get((j.id, eq_id), 0)
                if n > mejor.get(eq_id, 0):
                    mejor[eq_id] = n
        mejor_por_grupo[key] = mejor
    out = {}
    for j in juegos_dia:
        key = tuple(sorted((j.local_id, j.visita_id)))
        mejor = mejor_por_grupo.get(key, {})
        for eq_id in (j.local_id, j.visita_id):
            n_dir = directa.get((j.id, eq_id), 0)
            if n_dir:
                out[(j.id, eq_id)] = (n_dir, False)
            else:
                n_grp = mejor.get(eq_id, 0)
                out[(j.id, eq_id)] = (n_grp, bool(n_grp))
    return out


ALIN_POSICIONES = list(POSICIONES) + [('EH', 'Extra Hitter'), ('BD', 'Bateador Designado'), ('BA', 'Bateador Asignado')]
# Posiciones defensivas reales (únicas en el terreno). EH/BD/BA van al bate.
POS_DEFENSIVAS = [c for c, _ in POSICIONES]
# Slots extra que se dibujan en el terreno abajo-derecha: 1 designado + 5 asignados.
POS_EXTRA_TERRENO = ['BD', 'BA']
MAX_BATEADORES = 16  # 10 defensa + 1 designado + 5 asignados


class AlineacionDetalle(models.Model):
    alineacion = models.ForeignKey(Alineacion, on_delete=models.CASCADE, related_name='detalles')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='alineaciones_det')
    posicion = models.CharField(max_length=5, choices=ALIN_POSICIONES)
    orden_bateo = models.PositiveIntegerField(verbose_name='Turno al bate (1..16)')

    class Meta:
        unique_together = [('alineacion', 'jugador'), ('alineacion', 'orden_bateo')]
        ordering = ['orden_bateo']

    def __str__(self):
        return f"{self.orden_bateo}. {self.jugador} ({self.posicion})"


class PlantillaAlineacion(models.Model):
    """Plantilla reutilizable: guarda roster + rotación de bateo + posiciones."""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='plantillas')
    nombre = models.CharField(max_length=100)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        return f"{self.equipo} · {self.nombre}"


class PlantillaDetalle(models.Model):
    plantilla = models.ForeignKey(PlantillaAlineacion, on_delete=models.CASCADE, related_name='detalles')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE)
    posicion = models.CharField(max_length=5, choices=ALIN_POSICIONES)
    orden_bateo = models.PositiveIntegerField()

    class Meta:
        unique_together = [('plantilla', 'jugador'), ('plantilla', 'orden_bateo')]
        ordering = ['orden_bateo']


class AlineacionTitular(models.Model):
    """Titular regular del equipo: lo que se ve en la página pública.

    Separado de Alineacion (por juego). El capitán coloca 10 defensivos
    + 1 designado (BD) + 5 asignados (BA1..BA5).
    """
    equipo = models.OneToOneField(Equipo, on_delete=models.CASCADE, related_name='titular')
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actualizada = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Titular {self.equipo}"

    def por_posicion(self):
        return {d.posicion: d.jugador for d in self.detalles.select_related('jugador')}


# Slots del titular regular: 10 defensa + 1 designado + 5 asignados (códigos
# distintos para que cada slot sea único en el terreno).
TITULAR_POSICIONES = (list(POSICIONES) + [('BD', 'Bateador Designado')]
                      + [(f'BA{i}', f'Asignado {i}') for i in range(1, 6)])
TITULAR_DISP = {f'BA{i}': 'BA' for i in range(1, 6)}


class TitularDetalle(models.Model):
    titular = models.ForeignKey(AlineacionTitular, on_delete=models.CASCADE, related_name='detalles')
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='titular_det')
    posicion = models.CharField(max_length=5, choices=TITULAR_POSICIONES)

    class Meta:
        unique_together = [('titular', 'jugador'), ('titular', 'posicion')]

    def __str__(self):
        return f"{self.jugador} ({self.posicion})"
