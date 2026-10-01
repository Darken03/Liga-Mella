from django.db import models
from django.conf import settings

class Equipo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    sigla = models.CharField(max_length=5)
    color = models.CharField(max_length=20, default='#0A1A3A')
    capitan = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='equipos_capitaneados')
    director = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='equipos_dirigidos', verbose_name='Director (mismo poder que el capitán)')
    victorias = models.PositiveIntegerField(default=0)
    derrotas = models.PositiveIntegerField(default=0)
    abierto = models.BooleanField(default=True, verbose_name='Acepta nuevos jugadores')
    logo = models.ImageField(upload_to='equipos/', blank=True, null=True)
    banner = models.ImageField(upload_to='equipos/banners/', blank=True, null=True)
    banner_x = models.PositiveSmallIntegerField(default=50, verbose_name='Encuadre horizontal %')
    banner_y = models.PositiveSmallIntegerField(default=50, verbose_name='Encuadre vertical %')
    @property
    def banner_position(self):
        try:
            x = min(100, max(0, int(self.banner_x)))
        except Exception:
            x = 50
        try:
            y = min(100, max(0, int(self.banner_y)))
        except Exception:
            y = 50
        return f'{x}% {y}%'
    def save(self, *args, **kwargs):
        from core.imagenes import procesar_imagen_modelo, fotos_previas, borrar_si_reemplazada
        previas = fotos_previas(self, 'logo', 'banner')
        procesar_imagen_modelo(self, 'logo', 'banner')
        super().save(*args, **kwargs)
        borrar_si_reemplazada(self, previas)
    def __str__(self): return self.nombre
    @property
    def abridor(self):
        return self.jugadores.filter(posicion='P').first() or self.jugadores.first()
    @property
    def pct(self):
        t = self.victorias + self.derrotas
        return round(self.victorias / t, 3) if t else 0

POSICIONES = [('P','Pitcher'),('C','Catcher'),('1B','Primera'),('2B','Segunda'),('SS','Shortstop'),('3B','Tercera'),('LF','Left Field'),('LCF','Left-Center'),('RCF','Right-Center'),('RF','Right Field')]

class Jugador(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='jugadores')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True)
    dorsal = models.PositiveIntegerField(default=0, verbose_name='Núm. chaparreta')
    posicion = models.CharField(max_length=5, choices=POSICIONES, default='P')
    es_capitan = models.BooleanField(default=False)
    avg = models.FloatField(default=0)
    hr = models.PositiveIntegerField(default=0)
    rbi = models.PositiveIntegerField(default=0, verbose_name='Carreras impulsadas (CI)')
    era = models.FloatField(default=0, blank=True)
    foto = models.ImageField(upload_to='jugadores/', blank=True, null=True)
    portada = models.ImageField(upload_to='jugadores/portadas/', blank=True, null=True, verbose_name='Foto de portada')
    ci = models.CharField(max_length=30, blank=True, verbose_name='Carnet de identidad')
    edad = models.PositiveIntegerField(null=True, blank=True)
    estatura = models.CharField(max_length=10, blank=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='ficha_jugador')
    def save(self, *args, **kwargs):
        from core.imagenes import procesar_imagen_modelo, fotos_previas, borrar_si_reemplazada
        previas = fotos_previas(self, 'foto', 'portada')
        procesar_imagen_modelo(self, 'foto', 'portada')
        super().save(*args, **kwargs)
        borrar_si_reemplazada(self, previas)
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()
    def __str__(self): return f"{self.nombre_completo} #{self.dorsal} ({self.posicion})"
    class Meta:
        ordering = ['dorsal']


class SolicitudTraslado(models.Model):
    ESTADOS = [('pendiente','Pendiente'),('aceptada','Aceptada'),('rechazada','Rechazada')]
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='solicitudes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitudes_recibidas')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    mensaje = models.TextField(blank=True, verbose_name='Mensaje del capitán')
    creada = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='solicitudes_enviadas')
    def __str__(self): return f"{self.usuario} -> {self.equipo} ({self.estado})"
    class Meta: ordering = ['-creada']


def aceptar_solicitud(s):
    """El jugador acepta unirse al equipo: crea/actualiza su ficha.

    Devuelve False (sin guardar nada) si el equipo está cerrado.
    """
    equipo = s.equipo
    # Refresca por si la instancia viene desactualizada
    try:
        equipo.refresh_from_db(fields=['abierto'])
    except Exception:
        pass
    if not equipo.abierto:
        return False
    s.estado = 'aceptada'; s.save()
    u = s.usuario
    j, _ = Jugador.objects.get_or_create(usuario=u, defaults={'nombre': u.first_name or u.username, 'apellido': u.last_name, 'equipo': s.equipo})
    j.equipo = s.equipo; j.save()
    SolicitudTraslado.objects.filter(usuario=u, estado='pendiente').exclude(pk=s.pk).update(estado='rechazada')
    return j


# Al eliminar un equipo o jugador, sus imágenes se borran del disco
# (también cubre borrados en cascada). Ahorra espacio en media/.
from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=Equipo)
def _borrar_imgs_equipo(sender, instance, **kw):
    from core.imagenes import borrar_archivos
    borrar_archivos(instance, 'logo', 'banner')

@receiver(post_delete, sender=Jugador)
def _borrar_imgs_jugador(sender, instance, **kw):
    from core.imagenes import borrar_archivos
    borrar_archivos(instance, 'foto', 'portada')
