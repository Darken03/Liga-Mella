from django.db import models
from django.conf import settings
from equipos.models import Equipo

class Torneo(models.Model):
    nombre = models.CharField(max_length=120)
    temporada = models.CharField(max_length=50, default='Apertura 2026')
    fecha_inicio = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    playoffs_activos = models.BooleanField(default=False, verbose_name='Playoffs activos (visible en la página)')
    def __str__(self): return f"{self.nombre} {self.temporada}"

class Juego(models.Model):
    ESTADOS = [('programado','Programado'),('envivo','En vivo'),('final','Final')]
    MITADES = [('alta','Alta'),('baja','Baja')]
    FASES = [('regular','Regular'),('semifinal','Semifinal'),('final','Final')]
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='juegos')
    local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='juegos_local')
    visita = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='juegos_visita')
    fase = models.CharField(max_length=20, choices=FASES, default='regular', verbose_name='Fase')
    serie = models.CharField(max_length=20, blank=True, default='', verbose_name='Serie (SF1/SF2/F)')
    fecha = models.DateTimeField()
    estadio = models.CharField(max_length=100, default='Estadio Mella 1')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='programado')
    carreras_local = models.PositiveIntegerField(default=0)
    carreras_visita = models.PositiveIntegerField(default=0)
    inning_actual = models.CharField(max_length=20, default='1RA ALTA')
    inning_num = models.PositiveIntegerField(default=1)
    mitad = models.CharField(max_length=10, choices=MITADES, default='alta')
    outs = models.PositiveIntegerField(default=0)
    bolas = models.PositiveIntegerField(default=0)
    strikes = models.PositiveIntegerField(default=0)
    # índice del próximo bateador en cada lineup (0-based, rota)
    idx_local = models.PositiveIntegerField(default=0)
    idx_visita = models.PositiveIntegerField(default=0)
    pitcher_local = models.ForeignKey('equipos.Jugador', null=True, blank=True, on_delete=models.SET_NULL, related_name='juegos_pitcheados_local')
    pitcher_visita = models.ForeignKey('equipos.Jugador', null=True, blank=True, on_delete=models.SET_NULL, related_name='juegos_pitcheados_visita')
    anotador = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    def __str__(self): return f"{self.local} vs {self.visita} ({self.estado})"
    class Meta: ordering = ['-fecha']
    def sync_inning_txt(self):
        self.inning_actual = f"{self.inning_num}RA {'ALTA' if self.mitad == 'alta' else 'BAJA'}"
    @property
    def equipo_batea(self):
        # visita batea arriba, local abajo
        return self.visita if self.mitad == 'alta' else self.local
    @property
    def equipo_defiende(self):
        return self.local if self.mitad == 'alta' else self.visita

class EquipoTorneo(models.Model):
    """Récord de un equipo en un torneo: alimenta la tabla de posiciones."""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='lineas')
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='posiciones')
    ganados = models.PositiveIntegerField(default=0)
    perdidos = models.PositiveIntegerField(default=0)
    ca = models.PositiveIntegerField(default=0, verbose_name='Carreras anotadas')
    cp = models.PositiveIntegerField(default=0, verbose_name='Carreras permitidas')
    class Meta:
        unique_together = [('equipo', 'torneo')]
    @property
    def dif(self): return self.ca - self.cp
    @property
    def pct(self):
        t = self.ganados + self.perdidos
        return round(self.ganados / t, 3) if t else 0
    def __str__(self): return f"{self.equipo} en {self.torneo}: {self.ganados}-{self.perdidos}"


def _ranking(torneo):
    """Devuelve {equipo_id: posicion} con el mismo criterio de la tabla pública."""
    lineas = list(EquipoTorneo.objects.filter(torneo=torneo))
    orden = sorted(lineas, key=lambda l: (-l.ganados, -l.dif, -l.ca))
    return {l.equipo_id: i + 1 for i, l in enumerate(orden)}


def _usuarios_equipo(eq):
    """Capitán + director + jugadores con cuenta vinculada."""
    from usuarios.models import User
    from equipos.models import Jugador
    from django.db.models import Q
    users = list(User.objects.filter(
        Q(equipos_capitaneados=eq) | Q(equipos_dirigidos=eq)
        | Q(pk=eq.capitan_id) | Q(pk=eq.director_id)).distinct())
    for j in Jugador.objects.filter(equipo=eq, usuario__isnull=False).select_related('usuario'):
        if j.usuario and all(u.id != j.usuario.id for u in users):
            users.append(j.usuario)
    return users


def finalizar_juego(juego):
    """Al finalizar: actualiza totales históricos + línea del torneo + notifica.

    Los juegos de playoff (semifinal/final) NO tocan la tabla de posiciones
    de la fase regular; solo suman al historial del equipo y notifican.
    """
    es_playoff = juego.fase != 'regular'
    rank_antes = _ranking(juego.torneo)
    if juego.carreras_local > juego.carreras_visita:
        g, p = juego.local, juego.visita
    elif juego.carreras_visita > juego.carreras_local:
        g, p = juego.visita, juego.local
    else:
        g = p = None
    for eq, rol in ((juego.local, 'local'), (juego.visita, 'visita')):
        ca = juego.carreras_local if rol == 'local' else juego.carreras_visita
        cp = juego.carreras_visita if rol == 'local' else juego.carreras_local
        if g and eq == g: eq.victorias += 1
        elif g: eq.derrotas += 1
        eq.save()
        if es_playoff:
            continue
        lin, _ = EquipoTorneo.objects.get_or_create(equipo=eq, torneo=juego.torneo)
        if g and eq == g: lin.ganados += 1
        elif g: lin.perdidos += 1
        lin.ca += ca; lin.cp += cp; lin.save()
    # --- notificaciones de resultado + posición ---
    try:
        from notificaciones.models import crear_para_usuarios
        rank_despues = _ranking(juego.torneo)
        marcador = f"{juego.local.nombre} {juego.carreras_local}-{juego.carreras_visita} {juego.visita.nombre}"
        for eq in (juego.local, juego.visita):
            users = _usuarios_equipo(eq)
            if not users:
                continue
            if g is None:
                titulo = f"Empate: {marcador}"
                msg = f"Tu equipo empató en {juego.torneo.nombre}."
            elif eq.id == g.id:
                titulo = f"¡Ganaste! {marcador}"
                msg = f"Tu equipo ganó en {juego.torneo.nombre}."
            else:
                titulo = f"Perdiste: {marcador}"
                msg = f"Tu equipo perdió en {juego.torneo.nombre}."
            if es_playoff:
                fase_txt = dict(juego.FASES).get(juego.fase, juego.fase)
                msg += f" ({fase_txt} {juego.serie})."
                crear_para_usuarios(users, 'resultado', titulo, msg, url='/playoffs/')
                continue
            ra, rd = rank_antes.get(eq.id), rank_despues.get(eq.id)
            if ra and rd and ra != rd:
                if rd < ra:
                    msg += f" Subiste a la #{rd}."
                else:
                    msg += f" Bajaste a la #{rd}."
            elif rd:
                msg += f" Vas #{rd} en la tabla."
            crear_para_usuarios(users, 'resultado', titulo, msg, url='/posiciones/')
            # extra de posición si cambió
            if ra and rd and ra != rd:
                if rd < ra:
                    crear_para_usuarios(users, 'posicion', f"Subiste a la #{rd} 🎉", f"{eq.nombre} pasó de #{ra} a #{rd} en {juego.torneo.nombre}.", url='/posiciones/')
                else:
                    crear_para_usuarios(users, 'posicion', f"Bajaste a la #{rd}", f"{eq.nombre} pasó de #{ra} a #{rd} en {juego.torneo.nombre}.", url='/posiciones/')
    except Exception:
        pass


class Jugada(models.Model):
    RESULTADOS = [('hit','Hit sencillo'),('doble','Doble (2B)'),('triple','Triple (3B)'),('hr','Home Run'),('out','Out'),('k','Ponche (K)'),('bb','Base por bola'),('hbp','Golpeado'),('sf','Sacrificio'),('error','Error'),('fc',"Fielder's Choice (FC)"),('dp','Doble play (DP)'),('otro','Otro')]
    TIPOS = [('hit','Hit'),('out','Out'),('carrera','Carrera'),('bb','Base por bola'),('hr','Home Run'),('error','Error'),('otro','Otro')]
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='jugadas')
    inning = models.CharField(max_length=20, default='1')
    inning_num = models.PositiveIntegerField(default=1)
    mitad = models.CharField(max_length=10, default='alta')
    descripcion = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='otro')
    # turno detallado (nuevo sistema anotador)
    bateador = models.ForeignKey('equipos.Jugador', null=True, blank=True, on_delete=models.SET_NULL, related_name='turnos')
    pitcher = models.ForeignKey('equipos.Jugador', null=True, blank=True, on_delete=models.SET_NULL, related_name='turnos_pitcheados')
    equipo_batea = models.ForeignKey(Equipo, null=True, blank=True, on_delete=models.SET_NULL, related_name='turnos_bateo')
    resultado = models.CharField(max_length=20, choices=RESULTADOS, default='otro')
    rbi = models.PositiveIntegerField(default=0)
    carreras = models.PositiveIntegerField(default=0, verbose_name='Carreras en la jugada')
    # deltas aplicados a ActuacionBateo (para deshacer)
    d_ab = models.PositiveIntegerField(default=0); d_h = models.PositiveIntegerField(default=0)
    d_h2 = models.PositiveIntegerField(default=0); d_h3 = models.PositiveIntegerField(default=0)
    d_hr = models.PositiveIntegerField(default=0); d_r = models.PositiveIntegerField(default=0)
    d_rbi = models.PositiveIntegerField(default=0); d_bb = models.PositiveIntegerField(default=0)
    d_hbp = models.PositiveIntegerField(default=0); d_sf = models.PositiveIntegerField(default=0)
    d_kpit = models.PositiveIntegerField(default=0)
    # snapshot del juego antes del turno (para deshacer)
    s_outs = models.PositiveIntegerField(default=0); s_bolas = models.PositiveIntegerField(default=0)
    s_strikes = models.PositiveIntegerField(default=0); s_inning = models.PositiveIntegerField(default=1)
    s_mitad = models.CharField(max_length=10, default='alta')
    s_idx = models.PositiveIntegerField(default=0)
    s_cl = models.PositiveIntegerField(default=0); s_cv = models.PositiveIntegerField(default=0)
    creada = models.DateTimeField(auto_now_add=True)


class Entrada(models.Model):
    """Box-score por inning estilo MLB: carreras y hits por equipo."""
    juego = models.ForeignKey(Juego, on_delete=models.CASCADE, related_name='entradas')
    numero = models.PositiveIntegerField()
    carreras_local = models.PositiveIntegerField(default=0)
    carreras_visita = models.PositiveIntegerField(default=0)
    hits_local = models.PositiveIntegerField(default=0)
    hits_visita = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = [('juego', 'numero')]
        ordering = ['numero']
    def __str__(self): return f"{self.juego} INN {self.numero}"
