from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from equipos.models import Equipo, Jugador, SolicitudTraslado, aceptar_solicitud
from torneos.models import Torneo, Juego
from core.models import Noticia
from usuarios.models import User
from .forms import EquipoForm, JugadorForm, TorneoForm, JuegoForm, NoticiaForm

def solo_admin(u): return u.is_authenticated and (u.rol == 'admin' or u.is_superuser)

def adm(view):
    @login_required
    def w(request, *a, **k):
        if not solo_admin(request.user): return redirect('/cuenta/redirigir/')
        return view(request, *a, **k)
    return w

@adm
def dashboard(request):
    ctx = {'n_equipos': Equipo.objects.count(), 'n_jugadores': Jugador.objects.count(), 'n_juegos': Juego.objects.count(), 'n_usuarios': User.objects.count(),
           'n_pend': SolicitudTraslado.objects.filter(estado='pendiente').count(), 'juegos': Juego.objects.order_by('-fecha')[:5]}
    return render(request, 'administracion/dashboard.html', ctx)

# ---------- EQUIPOS ----------
@adm
def equipos(request):
    return render(request, 'administracion/equipos.html', {'equipos': Equipo.objects.all().order_by('nombre')})

@adm
def equipo_nuevo(request):
    f = EquipoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Equipo creado.'); return redirect('adm_equipos')
    return render(request, 'administracion/equipo_form.html', {'form': f, 'titulo': 'Añadir equipo'})

@adm
def equipo_detalle(request, pk):
    return render(request, 'administracion/equipo_detalle.html', {'equipo': get_object_or_404(Equipo, pk=pk)})

@adm
def equipo_editar(request, pk):
    e = get_object_or_404(Equipo, pk=pk)
    f = EquipoForm(request.POST or None, request.FILES or None, instance=e)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Equipo actualizado.'); return redirect('adm_equipos')
    return render(request, 'administracion/equipo_form.html', {'form': f, 'titulo': f'Editar {e.nombre}'})

@adm
def equipo_eliminar(request, pk):
    e = get_object_or_404(Equipo, pk=pk)
    if request.method == 'POST':
        e.delete(); messages.success(request, 'Equipo eliminado.'); return redirect('adm_equipos')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar equipo', 'objeto': e.nombre, 'volver': 'adm_equipos'})

@adm
def equipo_toggle(request, pk):
    """Abre o cierra un equipo a nuevos jugadores."""
    e = get_object_or_404(Equipo, pk=pk)
    if request.method == 'POST':
        e.abierto = not e.abierto
        e.save(update_fields=['abierto'])
        if e.abierto:
            messages.success(request, f'{e.nombre} está ABIERTO: acepta nuevos jugadores.')
        else:
            messages.warning(request, f'{e.nombre} está CERRADO: nadie puede entrar por ahora.')
    return redirect('adm_equipos')

@adm
def equipos_cerrar_todos(request):
    """Cierra todos los equipos de una vez (inicio de torneo)."""
    if request.method == 'POST':
        n = Equipo.objects.filter(abierto=True).update(abierto=False)
        messages.warning(request, f'Se cerraron {n} equipos: nadie puede entrar por ahora.')
    return redirect('adm_equipos')

@adm
def equipos_abrir_todos(request):
    """Abre todos los equipos de una vez."""
    if request.method == 'POST':
        n = Equipo.objects.filter(abierto=False).update(abierto=True)
        messages.success(request, f'Se abrieron {n} equipos: aceptan nuevos jugadores.')
    return redirect('adm_equipos')

# ---------- JUGADORES ----------
@adm
def jugadores(request):
    q = request.GET.get('eq', '')
    jugadores = Jugador.objects.all().order_by('equipo__nombre', 'dorsal')
    if q: jugadores = jugadores.filter(equipo_id=q)
    return render(request, 'administracion/jugadores.html', {'jugadores': jugadores, 'equipos': Equipo.objects.all(), 'eq': q})

@adm
def jugador_nuevo(request):
    f = JugadorForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Jugador añadido.'); return redirect('adm_jugadores')
    return render(request, 'administracion/jugador_form.html', {'form': f, 'titulo': 'Añadir jugador'})

@adm
def jugador_detalle(request, pk):
    from estadisticas.models import ActuacionBateo
    j = get_object_or_404(Jugador, pk=pk)
    return render(request, 'administracion/jugador_detalle.html', {'j': j, 'lineas': j.lineas.select_related('torneo'), 'torneos': Torneo.objects.all(), 'campos': ['ab', 'r', 'h', 'h2', 'h3', 'hr', 'rbi', 'bb', 'hbp', 'sf']})

@adm
def linea_guardar(request, pk):
    from estadisticas.models import ActuacionBateo
    j = get_object_or_404(Jugador, pk=pk)
    if request.method == 'POST':
        t = get_object_or_404(Torneo, pk=request.POST['torneo'])
        lin, _ = ActuacionBateo.objects.get_or_create(jugador=j, torneo=t)
        for f in ['ab', 'r', 'h', 'h2', 'h3', 'hr', 'rbi', 'bb', 'hbp', 'sf']:
            setattr(lin, f, int(request.POST.get(f) or 0))
        lin.save(); messages.success(request, f'Línea {t.nombre} guardada: AVG {lin.avg}.')
    return redirect('adm_jugador_detalle', pk=pk)

@adm
def jugador_editar(request, pk):
    j = get_object_or_404(Jugador, pk=pk)
    f = JugadorForm(request.POST or None, request.FILES or None, instance=j)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Jugador actualizado.'); return redirect('adm_jugadores')
    return render(request, 'administracion/jugador_form.html', {'form': f, 'titulo': f'Editar {j.nombre_completo}'})

@adm
def jugador_eliminar(request, pk):
    j = get_object_or_404(Jugador, pk=pk)
    if request.method == 'POST':
        j.delete(); messages.success(request, 'Jugador eliminado.'); return redirect('adm_jugadores')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar jugador', 'objeto': str(j), 'volver': 'adm_jugadores'})

# ---------- TORNEOS ----------
@adm
def torneos(request):
    return render(request, 'administracion/torneos.html', {'torneos': Torneo.objects.all()})

@adm
def torneo_nuevo(request):
    from torneos.sorteo import generar_sorteo, proximo_domingo_hoy
    equipos = Equipo.objects.all().order_by('nombre')
    if request.method == 'GET':
        f = TorneoForm(initial={'fecha_inicio': proximo_domingo_hoy()})
        return render(request, 'administracion/torneo_form.html',
                      {'form': f, 'titulo': 'Nuevo torneo', 'sorteo': True,
                       'equipos': equipos, 'hora_ini': 9})
    f = TorneoForm(request.POST)
    sel = [e for e in equipos if str(e.id) in request.POST.getlist('equipos')]
    try:
        hora_ini = int(request.POST.get('hora_inicio', 9))
    except (TypeError, ValueError):
        hora_ini = 9
    if not f.is_valid():
        return render(request, 'administracion/torneo_form.html',
                      {'form': f, 'titulo': 'Nuevo torneo', 'sorteo': True,
                       'equipos': equipos, 'hora_ini': hora_ini})
    if len(sel) < 2:
        messages.error(request, 'Selecciona al menos 2 equipos para el sorteo.')
        return render(request, 'administracion/torneo_form.html',
                      {'form': f, 'titulo': 'Nuevo torneo', 'sorteo': True,
                       'equipos': equipos, 'hora_ini': hora_ini})
    t = f.save(commit=False)
    if not t.fecha_inicio:
        t.fecha_inicio = proximo_domingo_hoy()
    t.save()
    fija_a, fija_b = _pareja_inaugural(request, sel)
    try:
        r = generar_sorteo(t, sel, fecha_inicio=t.fecha_inicio, hora_inicio=hora_ini,
                           fija_local=fija_a, fija_visita=fija_b)
        messages.success(request, f'Torneo creado + sorteo: {r["equipos"]} equipos, '
                                  f'{len(r["domingos"])} domingos, {r["juegos"]} juegos desde las {hora_ini}:00.')
        if fija_a and fija_b:
            ea = next(e for e in sel if e.id == fija_a)
            eb = next(e for e in sel if e.id == fija_b)
            messages.success(request, f'Inaugural: {ea.nombre} vs {eb.nombre} abren el torneo.')
    except ValueError as e:
        messages.warning(request, f'Torneo creado pero sin sorteo: {e}.')
        return redirect('adm_torneo_sorteo', pk=t.pk)
    return redirect('adm_torneo_detalle', pk=t.pk)


def _pareja_inaugural(request, sel):
    """Lee la pareja inaugural opcional del POST (ids) o (None, None.

    Los finalistas abren el campeonato: el sorteo los pone primeros sin
    agregar juegos extra.
    """
    try:
        a = int(request.POST.get('inaugural_local') or 0)
        b = int(request.POST.get('inaugural_visita') or 0)
    except (TypeError, ValueError):
        return None, None
    if not a or not b:
        return None, None
    if a == b:
        messages.error(request, 'El inaugural necesita dos equipos distintos.')
        return None, None
    sel_ids = {e.id for e in sel}
    if a not in sel_ids or b not in sel_ids:
        messages.error(request, 'Los equipos del inaugural deben estar en el sorteo.')
        return None, None
    return a, b

@adm
def torneo_sorteo(request, pk):
    """Generar/regenerar el sorteo eligiendo equipos (p. ej. si llegan nuevos).

    Solo permite regenerar si ningún juego empezó (todos programados);
    si ya hay juegos en vivo/final se bloquea para no borrar resultados.
    """
    from torneos.sorteo import generar_sorteo, proximo_domingo_hoy
    t = get_object_or_404(Torneo, pk=pk)
    equipos = Equipo.objects.all().order_by('nombre')
    en_juego = t.juegos.exclude(estado='programado').exists()
    if request.method == 'POST':
        if en_juego:
            messages.error(request, 'Ya hay juegos en vivo o finalizados: no se puede regenerar el sorteo.')
            return redirect('adm_torneo_detalle', pk=pk)
        sel = [e for e in equipos if str(e.id) in request.POST.getlist('equipos')]
        if len(sel) < 2:
            messages.error(request, 'Selecciona al menos 2 equipos.')
            return redirect('adm_torneo_sorteo', pk=pk)
        fi = request.POST.get('fecha_inicio') or (t.fecha_inicio.isoformat() if t.fecha_inicio else '')
        try:
            from datetime import datetime as _dt
            fi = _dt.strptime(fi, '%Y-%m-%d').date() if fi else proximo_domingo_hoy()
        except ValueError:
            fi = proximo_domingo_hoy()
        try:
            hora_ini = int(request.POST.get('hora_inicio', 9))
        except (TypeError, ValueError):
            hora_ini = 9
        t.juegos.all().delete()
        from torneos.models import EquipoTorneo
        EquipoTorneo.objects.filter(torneo=t).exclude(equipo__in=sel).delete()
        t.fecha_inicio = fi
        t.save(update_fields=['fecha_inicio'])
        fija_a, fija_b = _pareja_inaugural(request, sel)
        r = generar_sorteo(t, sel, fecha_inicio=fi, hora_inicio=hora_ini,
                           fija_local=fija_a, fija_visita=fija_b)
        messages.success(request, f'Sorteo generado: {r["equipos"]} equipos, '
                                  f'{len(r["domingos"])} domingos, {r["juegos"]} juegos desde las {hora_ini}:00.')
        if fija_a and fija_b:
            ea = next(e for e in sel if e.id == fija_a)
            eb = next(e for e in sel if e.id == fija_b)
            messages.success(request, f'Inaugural: {ea.nombre} vs {eb.nombre} abren el torneo.')
        return redirect('adm_torneo_detalle', pk=pk)
    dentro = set(t.juegos.values_list('local_id', flat=True)) | set(t.juegos.values_list('visita_id', flat=True))
    if not dentro:
        dentro = set(Equipo.objects.filter(lineas__torneo=t).values_list('id', flat=True))
    if not dentro:
        dentro = set(equipos.values_list('id', flat=True))
    return render(request, 'administracion/torneo_sorteo.html',
                  {'torneo': t, 'equipos': equipos, 'dentro': dentro, 'en_juego': en_juego,
                   'fecha_ini': (t.fecha_inicio.isoformat() if t.fecha_inicio else proximo_domingo_hoy().isoformat())})

@adm
def torneo_detalle(request, pk):
    from collections import OrderedDict
    from django.utils import timezone as _tz
    from torneos.models import EquipoTorneo
    t = get_object_or_404(Torneo, pk=pk)
    pos = sorted(EquipoTorneo.objects.filter(torneo=t).select_related('equipo'), key=lambda l: (-l.ganados, -l.dif, -l.ca))
    domingos = OrderedDict()
    for j in t.juegos.select_related('local', 'visita').order_by('fecha'):
        dia = _tz.localtime(j.fecha).date()
        domingos.setdefault(dia, []).append(j)
    # --- playoffs: semifinales 1v4/2v3 + final de ganadores ---
    juegos_po = list(t.juegos.filter(fase__in=['semifinal', 'final']).select_related('local', 'visita').order_by('fecha'))
    semis = [j for j in juegos_po if j.fase == 'semifinal']
    final = [j for j in juegos_po if j.fase == 'final']
    top4 = pos[:4]
    # fecha sugerida: domingo siguiente al último juego (10:00 y 12:00)
    from datetime import timedelta as _td
    try:
        ultimo = t.juegos.order_by('-fecha').first()
        base = _tz.localtime(ultimo.fecha).date() if ultimo else (t.fecha_inicio or _tz.localdate())
        d = base
        while d.weekday() != 6:
            d += _td(days=1)
        if ultimo and d <= _tz.localtime(ultimo.fecha).date():
            d += _td(days=7)
        fecha_sf1 = d.isoformat() + 'T10:00'
        fecha_sf2 = d.isoformat() + 'T12:00'
        fecha_fin = (d + _td(days=7)).isoformat() + 'T11:00'
    except Exception:
        fecha_sf1 = fecha_sf2 = fecha_fin = ''
    return render(request, 'administracion/torneo_detalle.html', {
        'torneo': t, 'juegos': t.juegos.order_by('-fecha'), 'posiciones': pos, 'domingos': domingos,
        'semis': semis, 'final': final, 'top4': top4,
        'fecha_sf1': fecha_sf1, 'fecha_sf2': fecha_sf2, 'fecha_fin': fecha_fin,
    })


def _ganador(juego):
    if juego.estado != 'final':
        return None
    if juego.carreras_local > juego.carreras_visita:
        return juego.local
    if juego.carreras_visita > juego.carreras_local:
        return juego.visita
    return None


@adm
def torneo_playoff(request, pk):
    """Genera semifinales (1v4, 2v3) y final (ganadores) de un torneo."""
    from django.utils import timezone as _tz
    from django.utils.dateparse import parse_datetime
    from torneos.models import EquipoTorneo
    t = get_object_or_404(Torneo, pk=pk)
    if request.method != 'POST':
        return redirect('adm_torneo_detalle', pk=pk)
    acc = request.POST.get('accion', '')

    def _parse_fecha(valor):
        dt = parse_datetime(valor or '')
        if dt is None:
            return None
        if _tz.is_naive(dt):
            dt = _tz.make_aware(dt, _tz.get_default_timezone())
        return dt

    if acc == 'generar_semis':
        if t.juegos.filter(fase='semifinal').exists():
            messages.error(request, 'Ya hay semifinales generadas. Elimínalas para regenerar.')
            return redirect('adm_torneo_detalle', pk=pk)
        pos = sorted(EquipoTorneo.objects.filter(torneo=t).select_related('equipo'),
                     key=lambda l: (-l.ganados, -l.dif, -l.ca))
        if len(pos) < 4:
            messages.error(request, 'Se necesitan al menos 4 equipos en la tabla para las semifinales.')
            return redirect('adm_torneo_detalle', pk=pk)
        e1, e2, e3, e4 = pos[0].equipo, pos[1].equipo, pos[2].equipo, pos[3].equipo
        f1, f2 = _parse_fecha(request.POST.get('fecha_sf1')), _parse_fecha(request.POST.get('fecha_sf2'))
        if not f1 or not f2:
            messages.error(request, 'Indica fecha y hora válidas para ambas semifinales.')
            return redirect('adm_torneo_detalle', pk=pk)
        estadio = (request.POST.get('estadio') or 'Estadio Mella 1').strip()[:100]
        Juego.objects.create(torneo=t, local=e1, visita=e4, fecha=f1, estadio=estadio, fase='semifinal', serie='SF1')
        Juego.objects.create(torneo=t, local=e2, visita=e3, fecha=f2, estadio=estadio, fase='semifinal', serie='SF2')
        messages.success(request, f'Semifinales listas: 1° {e1.nombre} vs 4° {e4.nombre} y 2° {e2.nombre} vs 3° {e3.nombre}.')
    elif acc == 'generar_final':
        if t.juegos.filter(fase='final').exists():
            messages.error(request, 'Ya hay final generada. Elimínala para regenerar.')
            return redirect('adm_torneo_detalle', pk=pk)
        semis = list(t.juegos.filter(fase='semifinal').select_related('local', 'visita').order_by('fecha'))
        if len(semis) < 2:
            messages.error(request, 'Primero genera las semifinales.')
            return redirect('adm_torneo_detalle', pk=pk)
        if any(s.estado != 'final' for s in semis):
            messages.error(request, 'Ambas semifinales deben estar en Final para crear la final.')
            return redirect('adm_torneo_detalle', pk=pk)
        g1, g2 = _ganador(semis[0]), _ganador(semis[1])
        if not g1 or not g2:
            messages.error(request, 'Hay una semifinal empatada: edita el marcador para definir un ganador.')
            return redirect('adm_torneo_detalle', pk=pk)
        ff = _parse_fecha(request.POST.get('fecha_fin'))
        if not ff:
            messages.error(request, 'Indica fecha y hora válidas para la final.')
            return redirect('adm_torneo_detalle', pk=pk)
        estadio = (request.POST.get('estadio_fin') or 'Estadio Mella 1').strip()[:100]
        Juego.objects.create(torneo=t, local=g1, visita=g2, fecha=ff, estadio=estadio, fase='final', serie='F')
        messages.success(request, f'Final lista: {g1.nombre} vs {g2.nombre}. ¡Que gane el mejor!')
    elif acc == 'eliminar_playoffs':
        n, _ = t.juegos.filter(fase__in=['semifinal', 'final']).delete()
        if t.playoffs_activos:
            t.playoffs_activos = False
            t.save(update_fields=['playoffs_activos'])
        messages.info(request, f'Playoffs eliminados ({n} juego(s)). Puedes regenerarlos.')
    elif acc == 'activar_playoffs':
        if not t.juegos.filter(fase='semifinal').exists():
            messages.error(request, 'Genera primero las semifinales con los clasificados para activar.')
            return redirect('adm_torneo_detalle', pk=pk)
        t.playoffs_activos = True
        t.save(update_fields=['playoffs_activos'])
        messages.success(request, 'Playoffs activados: ya se ven en la página pública.')
    elif acc == 'desactivar_playoffs':
        t.playoffs_activos = False
        t.save(update_fields=['playoffs_activos'])
        messages.info(request, 'Playoffs ocultos de la página pública.')
    else:
        messages.error(request, 'Acción inválida.')
    return redirect('adm_torneo_detalle', pk=pk)

@adm
def torneo_editar(request, pk):
    t = get_object_or_404(Torneo, pk=pk)
    f = TorneoForm(request.POST or None, instance=t)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Torneo actualizado.'); return redirect('adm_torneos')
    return render(request, 'administracion/torneo_form.html', {'form': f, 'titulo': f'Editar {t}'})

@adm
def torneo_eliminar(request, pk):
    t = get_object_or_404(Torneo, pk=pk)
    if request.method == 'POST':
        t.delete(); messages.success(request, 'Torneo eliminado.'); return redirect('adm_torneos')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar torneo', 'objeto': str(t), 'volver': 'adm_torneos'})

# ---------- JUEGOS ----------
@adm
def juegos(request):
    return render(request, 'administracion/juegos.html', {'juegos': Juego.objects.order_by('-fecha')})

@adm
def juego_detalle(request, pk):
    """Visualizar un juego con sus alineaciones (local + visita)."""
    from capitanes.models import get_alineacion_efectiva, POS_DEFENSIVAS
    j = get_object_or_404(Juego.objects.select_related('local', 'visita', 'torneo'), pk=pk)
    alin_local, prest_local, orig_local = get_alineacion_efectiva(j, j.local)
    alin_visita, prest_visita, orig_visita = get_alineacion_efectiva(j, j.visita)
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
    return render(request, 'administracion/juego_detalle.html', {
        'juego': j, 'alin_local': alin_local, 'alin_visita': alin_visita,
        'prest_local': prest_local, 'prest_visita': prest_visita,
        'orig_local': orig_local, 'orig_visita': orig_visita,
        'por_local': por_local, 'por_visita': por_visita,
        'por_bd_local': por_bd_local, 'por_ba_local': por_ba_local,
        'por_bd_visita': por_bd_visita, 'por_ba_visita': por_ba_visita,
        'entradas': list(j.entradas.order_by('numero')),
        'jugadas': j.jugadas.order_by('-id')[:30],
    })

@adm
def juego_nuevo(request):
    f = JuegoForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Juego creado.'); return redirect('adm_juegos')
    return render(request, 'administracion/juego_form.html', {'form': f, 'titulo': 'Programar juego'})

@adm
def juego_editar(request, pk):
    j = get_object_or_404(Juego, pk=pk)
    f = JuegoForm(request.POST or None, instance=j)
    if request.method == 'POST' and f.is_valid():
        f.save(); messages.success(request, 'Juego actualizado.'); return redirect('adm_juegos')
    return render(request, 'administracion/juego_form.html', {'form': f, 'titulo': f'Editar juego {j}'})

@adm
def juego_eliminar(request, pk):
    j = get_object_or_404(Juego, pk=pk)
    if request.method == 'POST':
        j.delete(); messages.success(request, 'Juego eliminado.'); return redirect('adm_juegos')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar juego', 'objeto': str(j), 'volver': 'adm_juegos'})

# ---------- NOTICIAS ----------
@adm
def noticias(request):
    return render(request, 'administracion/noticias.html', {'noticias': Noticia.objects.all()})

@adm
def noticia_nueva(request):
    f = NoticiaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and f.is_valid():
        n = f.save(commit=False)
        n.cuerpo = sanear_html(n.cuerpo or '')
        n.save(); messages.success(request, 'Noticia publicada.'); return redirect('adm_noticias')
    return render(request, 'administracion/noticia_form.html', {'form': f, 'titulo': 'Nueva noticia'})

@adm
def noticia_editar(request, pk):
    n = get_object_or_404(Noticia, pk=pk)
    f = NoticiaForm(request.POST or None, request.FILES or None, instance=n)
    if request.method == 'POST' and f.is_valid():
        n = f.save(commit=False)
        n.cuerpo = sanear_html(n.cuerpo or '')
        n.save(); messages.success(request, 'Noticia actualizada.'); return redirect('adm_noticias')
    return render(request, 'administracion/noticia_form.html', {'form': f, 'titulo': f'Editar: {n.titulo}'})

@adm
def noticia_eliminar(request, pk):
    n = get_object_or_404(Noticia, pk=pk)
    if request.method == 'POST':
        n.delete(); messages.success(request, 'Noticia eliminada.'); return redirect('adm_noticias')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar noticia', 'objeto': n.titulo, 'volver': 'adm_noticias'})

# ---------- HTML del editor (allowlist, sin dependencias) ----------
_HTML_PERMITIDO = {'p', 'h2', 'h3', 'h4', 'strong', 'b', 'em', 'i', 'u', 'a', 'ul', 'ol', 'li', 'blockquote', 'img', 'br', 'span'}
_ATTRS_PERMITIDOS = {'a': {'href', 'title', 'target'}, 'img': {'src', 'alt', 'style', 'width', 'height'}, 'span': {'style'}, 'p': {'style'}, 'h2': {'style'}, 'h3': {'style'}, 'h4': {'style'}, 'blockquote': {'style'}}
# Estilos permitidos por propiedad (para redimensionar fotos sin abrir XSS)
_ESTILOS_SEGUROS = {
    'font-size': r'[\w%#.\- ]+',
    'text-align': r'(left|center|right|justify)',
    'width': r'\d+(\.\d+)?(%|px)',
    'max-width': r'\d+(\.\d+)?(%|px)',
    'height': r'(auto|\d+(\.\d+)?(%|px))',
    'margin': r'[\w%#.\- ]+',
    'margin-left': r'(auto|[\w%#.\- ]+)',
    'margin-right': r'(auto|[\w%#.\- ]+)',
    'margin-top': r'[\w%#.\- ]+',
    'margin-bottom': r'[\w%#.\- ]+',
    'display': r'(block|inline|inline-block)',
    'border-radius': r'[\w%#.\- ]+',
    'float': r'(left|right|none)',
}

def _limpiar_style(valor):
    import re as _re
    limpias = []
    for parte in (valor or '').split(';'):
        parte = parte.strip()
        if not parte or ':' not in parte:
            continue
        prop, _, val = parte.partition(':')
        prop = prop.strip().lower()
        val = val.strip().lower().replace('!important', '').strip()
        patron = _ESTILOS_SEGUROS.get(prop)
        if not patron:
            continue
        if not _re.fullmatch(patron, val):
            continue
        # Límites sanos para ancho/alto
        if prop in ('width', 'max-width') and val.endswith('%'):
            try:
                if not (5 <= float(val[:-1]) <= 100):
                    continue
            except ValueError:
                continue
        limpias.append(f'{prop}: {val}')
    return '; '.join(limpias)

def sanear_html(html):
    from html.parser import HTMLParser
    import re
    class Limpieza(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.out = []
        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in ('script', 'style', 'iframe', 'object', 'embed', 'form'):
                self.out.append(None)  # marca para ignorar contenido
                return
            if tag not in _HTML_PERMITIDO:
                return
            limpios = []
            for k, v in attrs:
                k = k.lower()
                if k not in _ATTRS_PERMITIDOS.get(tag, set()):
                    continue
                v = (v or '').strip()
                if tag == 'a' and k == 'href' and not re.match(r'^(https?://|mailto:|/|#)', v):
                    continue
                if tag == 'img' and k == 'src' and not v.startswith(('/media/', '/static/', 'http')):
                    continue
                if tag == 'img' and k in ('width', 'height'):
                    if not re.fullmatch(r'\d+(\.\d+)?(%|px)?|auto', v.strip().lower()):
                        continue
                if k == 'style':
                    v = _limpiar_style(v)
                    if not v:
                        continue
                limpios.append(f'{k}="{v.replace(chr(34), "")}"')
            self.out.append(f"<{tag}{' ' + ' '.join(limpios) if limpios else ''}>")
        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag in _HTML_PERMITIDO:
                self.out.append(f"</{tag}>")
            elif tag in ('script', 'style', 'iframe'):
                self.out.append(None)
        def handle_data(self, data):
            # ignora texto dentro de tags bloqueados
            if self.out and self.out[-1] is None:
                return
            self.out.append(data)
        def texto(self):
            return ''.join(x for x in self.out if x is not None)
    p = Limpieza()
    try:
        p.feed(html or '')
    except Exception:
        return ''
    return p.texto()

@adm
def noticia_imagen_inline(request):
    from django.http import JsonResponse
    from django.core.files.storage import default_storage
    if request.method != 'POST' or 'imagen' not in request.FILES:
        return JsonResponse({'ok': False, 'error': 'Sube una imagen.'}, status=400)
    f = request.FILES['imagen']
    if f.size > 5 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'Máximo 5 MB.'}, status=400)
    # Toda imagen se convierte a WebP antes de guardar
    try:
        from core.imagenes import convertir_a_webp
        webp = convertir_a_webp(f)
    except Exception:
        webp = None
    if webp is not None:
        import uuid
        base = (webp.name or 'foto.webp').rsplit('.', 1)[0]
        nombre = f"noticias/{base}-{uuid.uuid4().hex[:8]}.webp"
        ruta = default_storage.save(nombre, webp)
    else:
        ruta = default_storage.save(f"noticias/{f.name}", f)
    return JsonResponse({'ok': True, 'url': default_storage.url(ruta)})

# ---------- USUARIOS ----------
@adm
def usuarios_list(request):
    return render(request, 'administracion/usuarios.html', {'usuarios': User.objects.all().order_by('username')})

def _guardar_usuario(request, u=None):
    d = request.POST
    if not u: u = User(username=d['username'])
    else: u.username = d['username']
    u.first_name = d.get('first_name', ''); u.last_name = d.get('last_name', '')
    u.rol = d.get('rol', 'fan'); u.ci = d.get('ci', ''); u.estatura = d.get('estatura', '')
    u.edad = int(d['edad']) if d.get('edad') else None
    if d.get('password'): u.set_password(d['password'])
    u.save()
    return u

@adm
def usuario_nuevo(request):
    if request.method == 'POST':
        if not request.POST.get('password'): messages.error(request, 'El password es obligatorio.'); return render(request, 'administracion/usuario_form.html', {'titulo': 'Nuevo usuario'})
        if User.objects.filter(username=request.POST['username']).exists(): messages.error(request, 'Ese username ya existe.'); return render(request, 'administracion/usuario_form.html', {'titulo': 'Nuevo usuario'})
        _guardar_usuario(request); messages.success(request, 'Usuario creado.'); return redirect('adm_usuarios')
    return render(request, 'administracion/usuario_form.html', {'titulo': 'Nuevo usuario'})

@adm
def usuario_editar(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        _guardar_usuario(request, u); messages.success(request, 'Usuario actualizado.'); return redirect('adm_usuarios')
    return render(request, 'administracion/usuario_form.html', {'titulo': f'Editar {u.username}', 'u': u})

@adm
def usuario_eliminar(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if u == request.user: messages.error(request, 'No puedes eliminarte a ti mismo.')
        else: u.delete(); messages.success(request, 'Usuario eliminado.')
        return redirect('adm_usuarios')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar usuario', 'objeto': u.username, 'volver': 'adm_usuarios'})

# ---------- SOLICITUDES ----------
@adm
def solicitudes(request):
    return render(request, 'administracion/solicitudes.html', {'solicitudes': SolicitudTraslado.objects.all()})

@adm
def solicitud_aprobar(request, pk):
    s = get_object_or_404(SolicitudTraslado, pk=pk)
    if request.method == 'POST':
        if not aceptar_solicitud(s):
            messages.error(request, f'{s.equipo.nombre} está cerrado: no se pueden aceptar jugadores ahora.')
            return redirect('adm_solicitudes')
        messages.success(request, f'{s.usuario} ahora juega con {s.equipo}.')
        try:
            from notificaciones.models import crear
            crear(s.usuario, 'fichaje_aceptado', f"¡Fuiste aceptado en {s.equipo.nombre}!",
                  f"Administración aprobó tu ingreso a {s.equipo.nombre}.", url='/cuenta/solicitudes/')
        except Exception:
            pass
    return redirect('adm_solicitudes')

@adm
def solicitud_rechazar(request, pk):
    s = get_object_or_404(SolicitudTraslado, pk=pk)
    if request.method == 'POST':
        s.estado = 'rechazada'; s.save()
        try:
            from notificaciones.models import crear
            crear(s.usuario, 'fichaje_rechazado', f"Solicitud a {s.equipo.nombre} rechazada",
                  "Administración rechazó la solicitud.", url='/cuenta/solicitudes/')
        except Exception:
            pass
    return redirect('adm_solicitudes')

# ---------- REGLAS ----------
@adm
def reglas(request):
    from core.models import Regla
    return render(request, 'administracion/reglas.html', {'reglas': Regla.objects.order_by('orden', 'id')})

@adm
def regla_nueva(request):
    from .forms import ReglaForm
    f = ReglaForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        r = f.save(commit=False)
        r.contenido = sanear_html(r.contenido or '')
        r.save(); messages.success(request, 'Regla publicada. Ya se ve en la página pública.'); return redirect('adm_reglas')
    return render(request, 'administracion/regla_form.html', {'form': f, 'titulo': 'Nueva regla'})

@adm
def regla_editar(request, pk):
    from core.models import Regla
    from .forms import ReglaForm
    r = get_object_or_404(Regla, pk=pk)
    f = ReglaForm(request.POST or None, instance=r)
    if request.method == 'POST' and f.is_valid():
        r = f.save(commit=False)
        r.contenido = sanear_html(r.contenido or '')
        r.save(); messages.success(request, 'Regla actualizada.'); return redirect('adm_reglas')
    return render(request, 'administracion/regla_form.html', {'form': f, 'titulo': f'Editar: {r.titulo}'})

@adm
def regla_eliminar(request, pk):
    from core.models import Regla
    r = get_object_or_404(Regla, pk=pk)
    if request.method == 'POST':
        r.delete(); messages.success(request, 'Regla eliminada.'); return redirect('adm_reglas')
    return render(request, 'administracion/confirmar_eliminar.html', {'titulo': 'Eliminar regla', 'objeto': r.titulo, 'volver': 'adm_reglas'})
