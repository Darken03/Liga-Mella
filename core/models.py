from django.db import models
class Noticia(models.Model):
    titulo = models.CharField(max_length=200)
    resumen = models.TextField()
    cuerpo = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    torneo_tag = models.CharField(max_length=100, default='TORNEO APERTURA')
    imagen = models.ImageField(upload_to='noticias/', blank=True, null=True)
    imagen2 = models.ImageField(upload_to='noticias/', blank=True, null=True, verbose_name='Imagen intermedia')
    video_youtube = models.URLField(max_length=500, blank=True, default='', verbose_name='Video de YouTube (URL)')
    @property
    def video_youtube_id(self):
        """Extrae el ID de YouTube desde watch, youtu.be, shorts, live o embed. None si no es válido."""
        import re
        from urllib.parse import urlparse, parse_qs
        url = (self.video_youtube or '').strip()
        if not url:
            return None
        # Compatibilidad: si pegan solo el ID de 11 caracteres
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', url):
            return url
        if not url.lower().startswith('http'):
            return None
        try:
            # Atajo robusto: busca el patrón en cualquier parte de la URL
            # (cubre watch?v=, youtu.be/, /shorts/, /live/, /embed/, /v/ y links de atribución)
            m = re.search(r'(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/|/v/)([A-Za-z0-9_-]{11})', url)
            if m:
                return m.group(1)
            p = urlparse(url)
            host = (p.hostname or '').lower()
            if host.startswith('www.'):
                host = host[4:]
            path = p.path or ''
            if host == 'youtu.be':
                vid = path.strip('/').split('/')[0] if path.strip('/') else ''
                if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid or ''):
                    return vid
                return None
            if host == 'youtube.com' or host.endswith('.youtube.com') or host == 'youtube-nocookie.com':
                if path.rstrip('/') == '/watch':
                    vid = (parse_qs(p.query).get('v') or [''])[0].strip()
                    if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid or ''):
                        return vid
                    return None
                for pref in ('/embed/', '/shorts/', '/live/', '/v/'):
                    if path.startswith(pref):
                        vid = path[len(pref):].strip('/').split('/')[0].split('?')[0]
                        if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid or ''):
                            return vid
                        return None
        except Exception:
            return None
        return None
    @property
    def video_embed_url(self):
        """URL del reproductor embebido de YouTube (o Facebook heredado) o None si no hay video válido."""
        from urllib.parse import quote
        vid = self.video_youtube_id
        if vid:
            return f'https://www.youtube-nocookie.com/embed/{vid}'
        # Compatibilidad con noticias antiguas que guardaron URL de Facebook
        url = (self.video_youtube or '').strip()
        if url.lower().startswith('http') and 'facebook.com' in url.lower():
            return f'https://www.facebook.com/plugins/video.php?href={quote(url, safe="")}&show_text=false'
        return None
    def save(self, *args, **kwargs):
        from .imagenes import procesar_imagen_modelo, fotos_previas, borrar_si_reemplazada
        previas = fotos_previas(self, 'imagen', 'imagen2')
        procesar_imagen_modelo(self, 'imagen', 'imagen2')
        super().save(*args, **kwargs)
        borrar_si_reemplazada(self, previas)
    def __str__(self): return self.titulo
    class Meta: ordering = ['-fecha']


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=Noticia)
def _borrar_imgs_noticia(sender, instance, **kw):
    from .imagenes import borrar_archivos
    borrar_archivos(instance, 'imagen', 'imagen2')


class Regla(models.Model):
    """Regla oficial de la liga: se muestra en la página pública /reglas/."""
    titulo = models.CharField(max_length=200)
    contenido = models.TextField(help_text='Texto de la regla (se admite formato básico).')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    activa = models.BooleanField(default=True, verbose_name='Visible en la página')
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Regla de la liga'
        verbose_name_plural = 'Reglas de la liga'

    def __str__(self): return self.titulo
