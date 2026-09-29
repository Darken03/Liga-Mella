from django.db import models
from django.conf import settings


class Notificacion(models.Model):
    TIPOS = [
        ('fichaje_recibido', 'Fichaje recibido'),
        ('fichaje_aceptado', 'Fichaje aceptado'),
        ('fichaje_rechazado', 'Fichaje rechazado'),
        ('resultado', 'Resultado de juego'),
        ('posicion', 'Cambio de posición'),
        ('sistema', 'Sistema'),
    ]
    ICONOS = {
        'fichaje_recibido': 'bi-person-plus',
        'fichaje_aceptado': 'bi-check-circle',
        'fichaje_rechazado': 'bi-x-circle',
        'resultado': 'bi-trophy',
        'posicion': 'bi-graph-up-arrow',
        'sistema': 'bi-megaphone',
    }
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=30, choices=TIPOS, default='sistema')
    titulo = models.CharField(max_length=150)
    mensaje = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=300, blank=True, default='')
    leida = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        return f"@{self.usuario.username}: {self.titulo}"

    @property
    def icono(self):
        return self.ICONOS.get(self.tipo, 'bi-bell')


def crear(usuario, tipo, titulo, mensaje='', url=''):
    """Crea una notificación salvo duplicado idéntico no leído reciente."""
    if usuario is None:
        return None
    # evita spam: si ya hay una igual no leída, no duplica
    if Notificacion.objects.filter(usuario=usuario, tipo=tipo, titulo=titulo, mensaje=mensaje, leida=False).exists():
        return None
    return Notificacion.objects.create(usuario=usuario, tipo=tipo, titulo=titulo, mensaje=mensaje, url=url)


def crear_para_usuarios(usuarios, tipo, titulo, mensaje='', url=''):
    creadas = []
    vistos = set()
    for u in usuarios:
        if u is None or u.id in vistos:
            continue
        vistos.add(u.id)
        n = crear(u, tipo, titulo, mensaje, url)
        if n:
            creadas.append(n)
    return creadas
