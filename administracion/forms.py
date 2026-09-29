from django import forms
from equipos.models import Equipo, Jugador
from torneos.models import Torneo, Juego
from core.models import Noticia, Regla

class BootForm(forms.ModelForm):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs['class'] = 'form-check-input'
            elif isinstance(w, forms.Select):
                w.attrs['class'] = 'form-select'
            elif isinstance(w, forms.ColorInput):
                w.attrs['class'] = 'form-control form-control-color w-100'
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs['class'] = 'form-control'
            elif isinstance(w, forms.Textarea):
                w.attrs.update({'class': 'form-control', 'rows': 3})
            else:
                w.attrs['class'] = 'form-control'

class EquipoForm(BootForm):
    class Meta:
        model = Equipo
        fields = ['nombre', 'sigla', 'color', 'logo', 'banner', 'banner_x', 'banner_y', 'capitan', 'director']
        widgets = {'color': forms.TextInput(attrs={'type': 'color'}),
                   'banner_x': forms.NumberInput(attrs={'type': 'range', 'min': 0, 'max': 100, 'step': 1, 'class': 'form-range w-100'}),
                   'banner_y': forms.NumberInput(attrs={'type': 'range', 'min': 0, 'max': 100, 'step': 1, 'class': 'form-range w-100'})}
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # BootForm pone form-control por defecto; los sliders necesitan form-range
        for n in ('banner_x', 'banner_y'):
            if n in self.fields:
                self.fields[n].widget.attrs['class'] = 'form-range w-100'

class JugadorForm(BootForm):
    class Meta:
        model = Jugador
        fields = ['nombre', 'apellido', 'foto', 'ci', 'edad', 'estatura', 'dorsal', 'posicion', 'equipo', 'usuario', 'avg', 'hr', 'rbi', 'era']

class TorneoForm(BootForm):
    class Meta:
        model = Torneo
        fields = ['nombre', 'temporada', 'fecha_inicio', 'activo']
        widgets = {'fecha_inicio': forms.DateInput(attrs={'type': 'date'})}

class JuegoForm(BootForm):
    class Meta:
        model = Juego
        fields = ['torneo', 'local', 'visita', 'fecha', 'estadio', 'estado', 'fase', 'anotador']
        widgets = {'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

class NoticiaForm(BootForm):
    class Meta:
        model = Noticia
        fields = ['titulo', 'torneo_tag', 'resumen', 'cuerpo', 'imagen', 'imagen2', 'video_youtube']
        widgets = {'cuerpo': forms.Textarea(attrs={'rows': 6}),
                   'video_youtube': forms.URLInput(attrs={'placeholder': 'https://www.youtube.com/watch?v=... o https://youtu.be/...'})}

    def clean_video_youtube(self):
        url = (self.cleaned_data.get('video_youtube') or '').strip()
        if not url:
            return ''
        # Acepta el ID suelto de 11 caracteres
        import re
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', url):
            return url
        tmp = Noticia(video_youtube=url)
        if tmp.video_youtube_id:
            return url
        # URLs heredadas de Facebook se siguen aceptando para no romper noticias viejas
        if 'facebook.com' in url.lower():
            return url
        raise forms.ValidationError(
            'Esa URL no es un video de YouTube valido. Abre el video en YouTube y copia su enlace: '
            'usa Compartir - Copiar enlace (https://youtu.be/...) o la barra del navegador '
            '(https://www.youtube.com/watch?v=...). No sirven paginas de busqueda, canales ni listas.'
        )


class ReglaForm(BootForm):
    class Meta:
        model = Regla
        fields = ['titulo', 'contenido', 'orden', 'activa']
        widgets = {'contenido': forms.Textarea(attrs={'rows': 8, 'placeholder': 'Escribe la regla... (una por tarjeta en la página pública)'})}
