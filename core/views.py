from django.shortcuts import render, get_object_or_404
from core.models import Noticia
from equipos.models import Equipo, Jugador
from torneos.models import Juego, Torneo

def home(request):
    noticias = Noticia.objects.all()[:3]
    envivo = Juego.objects.filter(estado='envivo')[:2]
    proximos = Juego.objects.filter(estado='programado').order_by('fecha')[:3]
    lideres = Jugador.objects.order_by('-avg')[:5]
    return render(request, 'core/home.html', {'noticias': noticias, 'envivo': envivo, 'proximos': proximos, 'lideres': lideres})

def noticias(request):
    return render(request, 'core/noticias.html', {'noticias': Noticia.objects.all()})

def noticia_detalle(request, pk):
    n = get_object_or_404(Noticia, pk=pk)
    relacionadas = Noticia.objects.exclude(pk=n.pk).order_by('-fecha')[:3]
    return render(request, 'core/noticia_detalle.html', {'n': n, 'relacionadas': relacionadas})

def juegos(request):
    from datetime import datetime, timedelta
    from django.utils import timezone
    hoy = timezone.localdate()
    juegos = list(Juego.objects.select_related('local', 'visita', 'torneo').order_by('fecha'))
    envivo = [j for j in juegos if j.estado == 'envivo']
    # --- almanaque de domingos: un domingo a la vez, con ◀ ▶ ---
    dias = sorted({timezone.localtime(j.fecha).date() for j in juegos})
    sel = request.GET.get('d', '')
    try:
        sel = datetime.strptime(sel, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        sel = None
    if sel is None:
        fut = [d for d in dias if d >= hoy]
        sel = fut[0] if fut else (dias[-1] if dias else hoy)
    ant = [d for d in dias if d < sel]
    sig = [d for d in dias if d > sel]
    dom_ant = ant[-1] if ant else None
    dom_sig = sig[0] if sig else None
    juegos_dia = sorted([j for j in juegos if timezone.localtime(j.fecha).date() == sel],
                        key=lambda j: (tuple(sorted((j.local_id, j.visita_id))), j.fecha))
    # etiquetas ida/vuelta por pareja del día + ficha de la jornada
    vistos = {}
    for j in juegos_dia:
        key = tuple(sorted((j.local_id, j.visita_id)))
        n = vistos.get(key, 0) + 1
        vistos[key] = n
        j.n_serie = n
        primero = [x for x in juegos_dia if tuple(sorted((x.local_id, x.visita_id))) == key][0]
        j.es_ida = (j.local_id == primero.local_id and j.visita_id == primero.visita_id)
    # orden cronológico para el cronograma + rotaciones ida/vuelta
    juegos_dia = sorted(juegos_dia, key=lambda j: j.fecha)
    rot_ida = [j for j in juegos_dia if j.es_ida]
    rot_vuelta = [j for j in juegos_dia if not j.es_ida]
    # alineaciones: conteo por juego para el bloque "Detalles"
    # (con fallback a la pareja ida/vuelta del mismo día)
    try:
        from capitanes.models import mapa_efectivo_juegos
        mapa = mapa_efectivo_juegos(juegos_dia)
        for j in juegos_dia:
            n_l, p_l = mapa.get((j.id, j.local_id), (0, False))
            n_v, p_v = mapa.get((j.id, j.visita_id), (0, False))
            j.n_alin_local = n_l
            j.n_alin_visita = n_v
            j.alin_local_prestada = p_l
            j.alin_visita_prestada = p_v
    except Exception:
        for j in juegos_dia:
            j.n_alin_local = 0
            j.n_alin_visita = 0
            j.alin_local_prestada = False
            j.alin_visita_prestada = False
    n_fin = sum(1 for j in juegos_dia if j.estado == 'final')
    if any(j.estado == 'envivo' for j in juegos_dia):
        est_dia = 'envivo'
    elif juegos_dia and all(j.estado == 'final' for j in juegos_dia):
        est_dia = 'final'
    else:
        est_dia = 'programado'
    return render(request, 'core/juegos.html', {
        'envivo': envivo, 'juegos_dia': juegos_dia, 'sel': sel,
        'dom_ant': dom_ant, 'dom_sig': dom_sig, 'dias': dias, 'hoy': hoy,
        'nj': dias.index(sel) + 1 if sel in dias else None,
        'n_fin': n_fin, 'est_dia': est_dia,
        'rot_ida': rot_ida, 'rot_vuelta': rot_vuelta,
    })

def posiciones(request):
    from torneos.models import EquipoTorneo
    torneos = Torneo.objects.all()
    tid = request.GET.get('torneo')
    t = Torneo.objects.filter(pk=tid).first() if tid else Torneo.objects.filter(activo=True).first() or Torneo.objects.first()
    lineas = sorted(EquipoTorneo.objects.filter(torneo=t).select_related('equipo'), key=lambda l: (-l.ganados, -l.dif, -l.ca)) if t else []
    playoffs_on = bool(t and t.playoffs_activos)
    return render(request, 'core/posiciones.html', {'torneo': t, 'torneos': torneos, 'lineas': lineas, 'playoffs_on': playoffs_on})


def reglas(request):
    from .models import Regla
    return render(request, 'core/reglas.html', {
        'reglas': Regla.objects.filter(activa=True).order_by('orden', 'id'),
    })


def playoffs(request):
    """Llave pública: semifinales 1v4/2v3 y final de ganadores por torneo.

    Solo se muestra si la administración activó los playoffs del torneo;
    si no, la página lo indica.
    """
    act = Torneo.objects.filter(playoffs_activos=True)
    tid = request.GET.get('torneo')
    t = act.filter(pk=tid).first() if tid else act.first()
    semis, final = [], []
    top4 = []
    if t:
        from torneos.models import EquipoTorneo
        lineas = sorted(EquipoTorneo.objects.filter(torneo=t).select_related('equipo'),
                        key=lambda l: (-l.ganados, -l.dif, -l.ca))
        top4 = lineas[:4]
        juegos_po = list(t.juegos.filter(fase__in=['semifinal', 'final'])
                         .select_related('local', 'visita').order_by('fecha'))
        semis = [j for j in juegos_po if j.fase == 'semifinal']
        final = [j for j in juegos_po if j.fase == 'final']
        for j in juegos_po:
            if j.estado == 'final':
                if j.carreras_local > j.carreras_visita:
                    j.ganador = j.local
                elif j.carreras_visita > j.carreras_local:
                    j.ganador = j.visita
                else:
                    j.ganador = None
            else:
                j.ganador = None
    return render(request, 'core/playoffs.html', {
        'torneo': t, 'torneos': act, 'semis': semis, 'final': final, 'top4': top4,
    })

def estadisticas(request):
    from estadisticas.models import ActuacionBateo
    from django.db.models import Sum, Count
    from equipos.models import Jugador
    ATTRS = ('ab', 'r', 'h', 'h2', 'h3', 'hr', 'rbi', 'bb', 'hbp', 'sf', 'k', 'avg', 'obp', 'slg', 'ops')
    torneos = Torneo.objects.all()
    tid = request.GET.get('torneo')
    q = request.GET.get('q', '')
    orden = request.GET.get('orden', '-avg')
    orden_h = request.GET.get('orden_h', '-hr')
    base_key = (orden or '-avg').lstrip('-')
    if base_key not in ATTRS:
        orden = '-avg'; base_key = 'avg'
    desc = (orden or '-avg').startswith('-')
    h_key = (orden_h or '-hr').lstrip('-')
    if h_key not in ATTRS:
        orden_h = '-hr'; h_key = 'hr'
    desc_h = (orden_h or '-hr').startswith('-')
    t = Torneo.objects.filter(pk=tid).first() if tid else Torneo.objects.filter(activo=True).first() or Torneo.objects.first()
    tab = request.GET.get('tab', 'lideres')
    if tab not in ('lideres', 'fama'):
        tab = 'lideres'
    lineas = ActuacionBateo.objects.filter(torneo=t).select_related('jugador', 'jugador__equipo') if t else []
    if q: lineas = lineas.filter(jugador__nombre__icontains=q)
    lineas = sorted(lineas, key=lambda l: getattr(l, base_key), reverse=desc)
    # --- Salón de la fama: acumulado histórico por jugador (todas las temporadas) ---
    agg = (ActuacionBateo.objects.values('jugador').annotate(
        ab=Sum('ab'), r=Sum('r'), h=Sum('h'), h2=Sum('h2'), h3=Sum('h3'), hr=Sum('hr'),
        rbi=Sum('rbi'), bb=Sum('bb'), hbp=Sum('hbp'), sf=Sum('sf'), k=Sum('k'),
        temps=Count('torneo', distinct=True)))
    jugadores = {j.id: j for j in Jugador.objects.select_related('equipo').filter(id__in=[a['jugador'] for a in agg])}
    fama = []
    for a in agg:
        j = jugadores.get(a['jugador'])
        if not j:
            continue
        ab = a['ab'] or 0; h = a['h'] or 0; bb = a['bb'] or 0; hbp = a['hbp'] or 0; sf = a['sf'] or 0
        h2 = a['h2'] or 0; h3 = a['h3'] or 0; hr = a['hr'] or 0
        tb = (h - h2 - h3 - hr) + 2 * h2 + 3 * h3 + 4 * hr
        avg = round(h / ab, 3) if ab else 0
        den = ab + bb + hbp + sf
        obp = round((h + bb + hbp) / den, 3) if den else 0
        slg = round(tb / ab, 3) if ab else 0
        ops = round(obp + slg, 3)
        fama.append({'jugador': j, 'ab': ab, 'r': a['r'] or 0, 'h': h, 'h2': h2, 'h3': h3,
                     'hr': hr, 'rbi': a['rbi'] or 0, 'bb': bb,
                     'hbp': hbp, 'sf': sf, 'k': a['k'] or 0, 'temps': a['temps'],
                     'avg': avg, 'obp': obp, 'slg': slg, 'ops': ops})
    if q:
        fama = [f for f in fama if q.lower() in f['jugador'].nombre.lower()]
    fama = sorted(fama, key=lambda f: f[h_key], reverse=desc_h)
    return render(request, 'core/estadisticas.html', {
        'torneo': t, 'torneos': torneos, 'lineas': lineas, 'q': q,
        'orden': orden, 'orden_h': orden_h, 'fama': fama, 'tab': tab,
    })

def equipos_list(request):
    return render(request, 'core/equipos.html', {'equipos': Equipo.objects.all()})


def juego_detalle(request, pk):
    """Detalle público del juego: marcador + box-score + alineaciones de ambos equipos."""
    juego = get_object_or_404(
        Juego.objects.select_related('local', 'visita', 'torneo'), pk=pk)
    from capitanes.models import get_alineacion_efectiva, POS_DEFENSIVAS
    alin_local, prest_local, orig_local = get_alineacion_efectiva(juego, juego.local)
    alin_visita, prest_visita, orig_visita = get_alineacion_efectiva(juego, juego.visita)
    def _por(alin):
        mapa, bd, ba = {}, None, []
        if alin:
            for d in alin.detalles.select_related('jugador').order_by('orden_bateo'):
                if d.posicion in POS_DEFENSIVAS and d.posicion not in mapa:
                    mapa[d.posicion] = d
                elif d.posicion == 'BD' and bd is None:
                    bd = d
                elif d.posicion == 'BA':
                    ba.append(d)
        return mapa, bd, ba
    por_local, por_bd_local, por_ba_local = _por(alin_local)
    por_visita, por_bd_visita, por_ba_visita = _por(alin_visita)
    entradas = list(juego.entradas.order_by('numero'))
    tot_hl = sum(e.hits_local for e in entradas)
    tot_hv = sum(e.hits_visita for e in entradas)
    jugadas = juego.jugadas.order_by('-id')[:30]
    return render(request, 'core/juego_detalle.html', {
        'juego': juego,
        'alin_local': alin_local, 'alin_visita': alin_visita,
        'prest_local': prest_local, 'prest_visita': prest_visita,
        'orig_local': orig_local, 'orig_visita': orig_visita,
        'por_local': por_local, 'por_visita': por_visita,
        'por_bd_local': por_bd_local, 'por_ba_local': por_ba_local,
        'por_bd_visita': por_bd_visita, 'por_ba_visita': por_ba_visita,
        'entradas': entradas, 'tot_hl': tot_hl, 'tot_hv': tot_hv,
        'jugadas': jugadas,
    })

def equipo_detalle(request, pk):
    from torneos.models import EquipoTorneo
    from equipos.models import SolicitudTraslado
    from django.contrib import messages
    from django.shortcuts import redirect
    equipo = get_object_or_404(Equipo, pk=pk)
    # POST: jugador pide unirse al equipo
    if request.method == 'POST' and request.POST.get('accion') == 'pedir_unirse':
        if not request.user.is_authenticated:
            messages.info(request, 'Inicia sesión para pedir unirte.')
            return redirect(f"/cuenta/login/?next=/equipos/{equipo.id}/")
        # ya está en este equipo?
        if hasattr(request.user, 'ficha_jugador') and request.user.ficha_jugador and request.user.ficha_jugador.equipo_id == equipo.id:
            messages.info(request, 'Ya juegas en este equipo.')
        else:
            ex = SolicitudTraslado.objects.filter(equipo=equipo, usuario=request.user, estado='pendiente').first()
            if ex:
                messages.info(request, 'Ya tienes una solicitud pendiente con este equipo.')
            else:
                SolicitudTraslado.objects.create(equipo=equipo, usuario=request.user, estado='pendiente', creado_por=request.user)
                try:
                    from notificaciones.models import crear_para_usuarios
                    from usuarios.models import User as U
                    from django.db.models import Q
                    caps = list(U.objects.filter(Q(equipos_capitaneados=equipo) | Q(equipos_dirigidos=equipo) | Q(pk=equipo.capitan_id) | Q(pk=equipo.director_id)).distinct())
                    crear_para_usuarios(caps, 'fichaje_recibido', f"@{request.user.username} quiere unirse a {equipo.nombre}",
                                        f"{request.user.username} pidió unirse a tu equipo. Revísalo en Fichajes.", url='/capitan/fichajes/')
                except Exception:
                    pass
                messages.success(request, f'Pediste unirte a {equipo.nombre}. El capitán la verá en Fichajes.')
        return redirect('equipo_detalle', pk=equipo.id)
    jugadores = equipo.jugadores.all()
    actual = Torneo.objects.filter(activo=True).first()
    linea = EquipoTorneo.objects.filter(equipo=equipo, torneo=actual).first() if actual else None
    historial = EquipoTorneo.objects.filter(equipo=equipo).select_related('torneo')
    pmap = {}
    for j in sorted(jugadores, key=lambda x: (0 if x.es_capitan else 1, x.dorsal)):
        pmap.setdefault(j.posicion, j)
    # Titular regular configurado por el capitán: manda sobre el pmap automático
    por_bd_tit, por_ba_tit = None, [None] * 5
    try:
        tit = getattr(equipo, 'titular', None)
        if tit is not None:
            det = list(tit.detalles.select_related('jugador'))
            if det:
                pmap = {d.posicion: d.jugador for d in det}
                por_bd_tit = pmap.get('BD')
                por_ba_tit = [pmap.get(f'BA{i}') for i in range(1, 6)]
    except Exception:
        pass
    capitan = jugadores.filter(es_capitan=True).first()
    mi_solicitud = None
    en_equipo = False
    if request.user.is_authenticated:
        from equipos.models import Jugador
        en_equipo = Jugador.objects.filter(equipo=equipo, usuario=request.user).exists()
        mi_solicitud = SolicitudTraslado.objects.filter(equipo=equipo, usuario=request.user, estado='pendiente').first()
    return render(request, 'core/equipo_detalle.html', {'equipo': equipo, 'jugadores': jugadores, 'pmap': pmap, 'por_bd_tit': por_bd_tit, 'por_ba_tit': por_ba_tit, 'capitan': capitan, 'linea': linea, 'historial': historial, 'actual': actual, 'mi_solicitud': mi_solicitud, 'en_equipo': en_equipo})

def _totales_jugador(jugador_id):
    """Acumulado histórico de un jugador (todas las temporadas)."""
    from estadisticas.models import ActuacionBateo
    from django.db.models import Sum, Count
    agg = (ActuacionBateo.objects.filter(jugador_id=jugador_id).aggregate(
        ab=Sum('ab'), r=Sum('r'), h=Sum('h'), h2=Sum('h2'), h3=Sum('h3'), hr=Sum('hr'),
        rbi=Sum('rbi'), bb=Sum('bb'), hbp=Sum('hbp'), sf=Sum('sf'), k=Sum('k'),
        temps=Count('torneo', distinct=True)))
    ab = agg['ab'] or 0; h = agg['h'] or 0; bb = agg['bb'] or 0
    hbp = agg['hbp'] or 0; sf = agg['sf'] or 0
    h2 = agg['h2'] or 0; h3 = agg['h3'] or 0; hr = agg['hr'] or 0
    tb = (h - h2 - h3 - hr) + 2 * h2 + 3 * h3 + 4 * hr
    avg = round(h / ab, 3) if ab else 0
    den = ab + bb + hbp + sf
    obp = round((h + bb + hbp) / den, 3) if den else 0
    slg = round(tb / ab, 3) if ab else 0
    return {'ab': ab, 'r': agg['r'] or 0, 'h': h, 'h2': h2, 'h3': h3,
            'hr': hr, 'rbi': agg['rbi'] or 0, 'bb': bb, 'hbp': hbp,
            'sf': sf, 'k': agg['k'] or 0, 'temps': agg['temps'] or 0,
            'avg': avg, 'obp': obp, 'slg': slg, 'ops': round(obp + slg, 3)}


def jugador_detalle(request, pk):
    """Perfil público del jugador: foto, portada, equipo y sus estadísticas."""
    j = get_object_or_404(Jugador.objects.select_related('equipo'), pk=pk)
    lineas = j.lineas.select_related('torneo').order_by('-torneo__id')
    return render(request, 'core/jugador_detalle.html', {
        'j': j, 'lineas': lineas, 'tot': _totales_jugador(j.id),
    })

def ui_kit(request):
    return render(request, 'core/ui_kit.html')
