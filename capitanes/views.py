from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from torneos.models import Juego, Torneo
from equipos.models import Equipo, Jugador, SolicitudTraslado, aceptar_solicitud, POSICIONES
from estadisticas.models import ActuacionBateo
from usuarios.models import User
from .models import Alineacion, AlineacionDetalle, PlantillaAlineacion, PlantillaDetalle, AlineacionTitular, TitularDetalle, ALIN_POSICIONES, POS_DEFENSIVAS, TITULAR_POSICIONES


EQUIPO_ADMIN_SESSION_KEY = 'equipo_admin_id'


def es_admin_user(u):
    return u.is_authenticated and (getattr(u, 'rol', '') == 'admin' or u.is_superuser)


def equipo_admin_activo(request):
    """Equipo que el admin eligió administrar en esta sesión (o None)."""
    if not es_admin_user(request.user):
        return None
    try:
        eid = int(request.session.get(EQUIPO_ADMIN_SESSION_KEY) or 0)
    except (TypeError, ValueError):
        return None
    if not eid:
        return None
    return Equipo.objects.filter(pk=eid).first()


def mi_equipo(request):
    if es_admin_user(request.user):
        sel = equipo_admin_activo(request)
        if sel is not None:
            return sel
        # admin sin selección: no adivinar equipo, pide elegir
        return None
    eq = request.user.equipos_capitaneados.first()
    if eq is None:
        eq = request.user.equipos_dirigidos.first()
    return eq or Equipo.objects.first()


def _torneo_actual(request):
    tid = request.GET.get('torneo')
    if tid:
        return Torneo.objects.filter(pk=tid).first()
    return Torneo.objects.filter(activo=True).first() or Torneo.objects.first()


# ---------- PANEL ----------
@login_required
def dashboard(request):
    eq = mi_equipo(request)
    if eq:
        prox = Juego.objects.filter(Q(local=eq) | Q(visita=eq), estado='programado').order_by('fecha')[:3]
        pend_fich = SolicitudTraslado.objects.filter(equipo=eq, estado='pendiente').count()
        n_jug = eq.jugadores.count()
    else:
        prox, pend_fich, n_jug = [], 0, 0
    enviadas = SolicitudTraslado.objects.filter(creado_por=request.user).order_by('-creada')[:5]
    return render(request, 'capitanes/dashboard.html', {
        'equipo': eq, 'juegos': prox, 'enviadas': enviadas,
        'pend_fich': pend_fich, 'n_jug': n_jug,
    })


@login_required
def seleccionar_equipo(request):
    """Interfaz intermedia del admin: elige qué equipo administrar.

    GET = tarjetas de equipos. POST con equipo_id = fija en sesión.
    POST con equipo_id vacío = limpia la selección.
    """
    if not es_admin_user(request.user):
        messages.error(request, 'Solo el administrador puede elegir equipo.')
        return redirect('cap_dash')
    if request.method == 'POST':
        raw = (request.POST.get('equipo_id') or '').strip()
        if not raw:
            request.session.pop(EQUIPO_ADMIN_SESSION_KEY, None)
            messages.info(request, 'Dejaste de administrar equipos.')
            return redirect('cap_seleccionar')
        try:
            eid = int(raw)
        except (TypeError, ValueError):
            messages.error(request, 'Equipo inválido.')
            return redirect('cap_seleccionar')
        eq = Equipo.objects.filter(pk=eid).first()
        if not eq:
            request.session.pop(EQUIPO_ADMIN_SESSION_KEY, None)
            messages.error(request, 'Ese equipo ya no existe.')
            return redirect('cap_seleccionar')
        request.session[EQUIPO_ADMIN_SESSION_KEY] = eq.id
        messages.success(request, f'Administrando a {eq.nombre} como capitán.')
        return redirect('cap_dash')
    q = (request.GET.get('q') or '').strip()
    equipos = Equipo.objects.all().order_by('nombre')
    if q:
        equipos = equipos.filter(nombre__icontains=q)
    return render(request, 'capitanes/seleccionar.html', {
        'equipos': equipos, 'q': q,
        'actual': equipo_admin_activo(request),
    })


@login_required
def fijar_equipo(request, pk):
    """Atajo GET desde las tarjetas: fija el equipo y entra al panel."""
    if not es_admin_user(request.user):
        messages.error(request, 'Solo el administrador puede elegir equipo.')
        return redirect('cap_dash')
    eq = get_object_or_404(Equipo, pk=pk)
    request.session[EQUIPO_ADMIN_SESSION_KEY] = eq.id
    messages.success(request, f'Administrando a {eq.nombre} como capitán.')
    return redirect('cap_dash')


@login_required
def mis_stats(request):
    """Mis estadísticas: si el capitán/director tiene ficha en su equipo,
    va a su perfil de jugador; si no, al roster con sus números."""
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    ficha = getattr(request.user, 'ficha_jugador', None)
    if ficha is not None and ficha.equipo_id == eq.id:
        return redirect('cap_jugador_detalle', pk=ficha.id)
    messages.info(request, 'Tu cuenta no tiene ficha de jugador en este equipo: ves el roster con sus números.')
    return redirect('cap_jugadores')


# ---------- JUGADORES ----------
@login_required
def jugadores(request):
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    torneos = Torneo.objects.all()
    t = _torneo_actual(request)
    # líneas del torneo actual para ordenar por AVG
    lineas_map = {}
    if t:
        for lin in ActuacionBateo.objects.filter(torneo=t, jugador__equipo=eq).select_related('jugador'):
            lineas_map[lin.jugador_id] = lin
    roster = list(eq.jugadores.all())
    for j in roster:
        j.linea_actual = lineas_map.get(j.id)
        j.avg_actual = j.linea_actual.avg if j.linea_actual else (j.avg or 0)
        j.ops_actual = j.linea_actual.ops if j.linea_actual else 0
    roster.sort(key=lambda j: (-(j.avg_actual or 0), -(j.ops_actual or 0), j.nombre))
    return render(request, 'capitanes/jugadores.html', {
        'equipo': eq, 'roster': roster, 'torneo': t, 'torneos': torneos,
    })


@login_required
def jugador_detalle(request, pk):
    eq = mi_equipo(request)
    j = get_object_or_404(Jugador, pk=pk, equipo=eq)
    lineas = j.lineas.select_related('torneo').order_by('-torneo__id')
    actual = Torneo.objects.filter(activo=True).first()
    linea_actual = j.lineas.filter(torneo=actual).first() if actual else None
    return render(request, 'capitanes/jugador_detalle.html', {
        'equipo': eq, 'j': j, 'lineas': lineas, 'linea_actual': linea_actual, 'actual': actual,
    })


@login_required
def jugador_expulsar(request, pk):
    eq = mi_equipo(request)
    j = get_object_or_404(Jugador, pk=pk, equipo=eq)
    if request.method == 'POST':
        if j.es_capitan:
            messages.error(request, 'No puedes expulsar al capitán.')
        else:
            nombre = j.nombre_completo
            # desvincular cuenta si existe para que pueda fichar por otro equipo
            if j.usuario_id:
                # eliminamos la ficha; el User queda libre
                pass
            j.delete()
            messages.success(request, f'{nombre} fue expulsado del equipo.')
        return redirect('cap_jugadores')
    return render(request, 'capitanes/jugador_expulsar.html', {'equipo': eq, 'j': j})


# ---------- JUEGOS ----------
@login_required
def juegos(request):
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    torneos = Torneo.objects.all()
    t = _torneo_actual(request)
    base = Juego.objects.filter(Q(local=eq) | Q(visita=eq))
    if t:
        base = base.filter(torneo=t)
    pendientes = base.filter(estado__in=['programado', 'envivo']).order_by('fecha')
    anteriores = base.filter(estado='final').order_by('-fecha')
    return render(request, 'capitanes/juegos.html', {
        'equipo': eq, 'torneo': t, 'torneos': torneos,
        'pendientes': pendientes, 'anteriores': anteriores,
    })


@login_required
def juego_detalle(request, pk):
    eq = mi_equipo(request)
    juego = get_object_or_404(Juego, pk=pk)
    if eq and juego.local_id != eq.id and juego.visita_id != eq.id:
        messages.error(request, 'Ese juego no es de tu equipo.')
        return redirect('cap_juegos')
    jugadas = juego.jugadas.order_by('-id')[:30]
    # alineaciones guardadas para este juego (con fallback a la pareja ida/vuelta)
    from .models import get_alineacion_efectiva, POS_DEFENSIVAS
    if eq:
        alin_mia, prest_mia, orig_mia = get_alineacion_efectiva(juego, eq)
    else:
        alin_mia, prest_mia, orig_mia = None, False, None
    rival = juego.visita if eq and juego.local_id == eq.id else juego.local
    if rival:
        alin_rival, prest_rival, orig_rival = get_alineacion_efectiva(juego, rival)
    else:
        alin_rival, prest_rival, orig_rival = None, False, None
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
    _pm, _pbd_m, _pba_m = _por(alin_mia)
    _pr, _pbd_r, _pba_r = _por(alin_rival)
    por_mia, por_bd_mia, por_ba_mia = _pm, _pbd_m, _pba_m
    por_rival, por_bd_rival, por_ba_rival = _pr, _pbd_r, _pba_r
    # líderes / stats del torneo del juego
    t = juego.torneo
    def stats_equipo(equipo):
        lineas = list(ActuacionBateo.objects.filter(torneo=t, jugador__equipo=equipo).select_related('jugador'))
        if not lineas:
            return {'batearon': [], 'mejor': None, 'mas_rbi': None, 'mas_hr': None}
        batearon = sorted(lineas, key=lambda l: (-l.avg, -l.ops))
        mejor = max(lineas, key=lambda l: (l.avg, l.ops))
        mas_rbi = max(lineas, key=lambda l: (l.rbi, l.hr))
        mas_hr = max(lineas, key=lambda l: (l.hr, l.rbi))
        return {'batearon': batearon, 'mejor': mejor, 'mas_rbi': mas_rbi, 'mas_hr': mas_hr}
    stats_mias = stats_equipo(eq) if eq else None
    stats_rival = stats_equipo(rival) if rival else None
    es_local = eq and juego.local_id == eq.id
    mi_score = juego.carreras_local if es_local else juego.carreras_visita
    rival_score = juego.carreras_visita if es_local else juego.carreras_local
    resultado = None
    if juego.estado == 'final':
        if mi_score > rival_score:
            resultado = 'ganado'
        elif mi_score < rival_score:
            resultado = 'perdido'
        else:
            resultado = 'empate'
    return render(request, 'capitanes/juego_detalle.html', {
        'equipo': eq, 'juego': juego, 'jugadas': jugadas,
        'alin_mia': alin_mia, 'alin_rival': alin_rival, 'rival': rival,
        'prest_mia': prest_mia, 'prest_rival': prest_rival,
        'orig_mia': orig_mia, 'orig_rival': orig_rival,
        'por_mia': por_mia, 'por_rival': por_rival,
        'por_bd_mia': por_bd_mia, 'por_ba_mia': por_ba_mia,
        'por_bd_rival': por_bd_rival, 'por_ba_rival': por_ba_rival,
        'stats_mias': stats_mias, 'stats_rival': stats_rival,
        'es_local': es_local, 'resultado': resultado,
    })


# ---------- FICHAJES ----------
@login_required
def fichajes(request):
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    entrantes = SolicitudTraslado.objects.filter(equipo=eq, estado='pendiente').select_related('usuario', 'creado_por').order_by('-creada')
    historial = SolicitudTraslado.objects.filter(equipo=eq).exclude(estado='pendiente').select_related('usuario').order_by('-creada')[:15]
    enviadas = SolicitudTraslado.objects.filter(equipo=eq, creado_por=request.user).order_by('-creada')[:20]
    # usuarios disponibles para solicitar (que no estén ya en mi equipo)
    en_equipo_ids = set(Jugador.objects.filter(equipo=eq, usuario__isnull=False).values_list('usuario_id', flat=True))
    usuarios = User.objects.exclude(pk__in=en_equipo_ids).order_by('username')[:200]
    return render(request, 'capitanes/fichajes.html', {
        'equipo': eq, 'entrantes': entrantes, 'historial': historial,
        'enviadas': enviadas, 'usuarios': usuarios,
    })


@login_required
def solicitar(request):
    eq = mi_equipo(request)
    if eq is not None and not eq.abierto:
        messages.error(request, f'{eq.nombre} está cerrado: no puedes invitar jugadores mientras esté cerrado.')
        return redirect('cap_fichajes')
    if request.method == 'POST':
        u = get_object_or_404(User, pk=request.POST['usuario'])
        if hasattr(u, 'ficha_jugador') and u.ficha_jugador and u.ficha_jugador.equipo_id == (eq.id if eq else None):
            messages.info(request, 'Ese jugador ya está en tu equipo.')
        else:
            ex = SolicitudTraslado.objects.filter(equipo=eq, usuario=u, estado='pendiente').first()
            if ex:
                messages.info(request, f'Ya hay una solicitud pendiente para {u.username}.')
            else:
                mensaje = (request.POST.get('mensaje') or '').strip()[:500]
                SolicitudTraslado.objects.create(equipo=eq, usuario=u, estado='pendiente', creado_por=request.user, mensaje=mensaje)
                try:
                    from notificaciones.models import crear
                    texto = f"El capitán @{request.user.username} te invitó a {eq.nombre}."
                    if mensaje:
                        texto += f' Dice: "{mensaje}"'
                    texto += " Revísala en Mis solicitudes."
                    crear(u, 'fichaje_recibido', f"{eq.nombre} te solicitó unirte a su equipo", texto,
                          url='/cuenta/solicitudes/')
                except Exception:
                    pass
                messages.success(request, f'Solicitud enviada a {u.username}. Debe aceptarla en Mi cuenta → Mis solicitudes.')
        return redirect('cap_fichajes')
    return redirect('cap_fichajes')


@login_required
def fichaje_aprobar(request, pk):
    eq = mi_equipo(request)
    s = get_object_or_404(SolicitudTraslado, pk=pk, equipo=eq, estado='pendiente')
    if request.method == 'POST':
        if not aceptar_solicitud(s):
            messages.error(request, f'{eq.nombre} está cerrado: no se pueden aceptar jugadores ahora.')
            return redirect('cap_fichajes')
        try:
            from notificaciones.models import crear
            crear(s.usuario, 'fichaje_aceptado', f"¡Fuiste aceptado en {eq.nombre}!",
                  f"El capitán aprobó tu solicitud. Ya eres parte de {eq.nombre}.", url='/cuenta/solicitudes/')
        except Exception:
            pass
        messages.success(request, f'{s.usuario.username} ahora juega con {eq.nombre}.')
    return redirect('cap_fichajes')


@login_required
def fichaje_rechazar(request, pk):
    eq = mi_equipo(request)
    s = get_object_or_404(SolicitudTraslado, pk=pk, equipo=eq, estado='pendiente')
    if request.method == 'POST':
        s.estado = 'rechazada'
        s.save()
        try:
            from notificaciones.models import crear
            crear(s.usuario, 'fichaje_rechazado', f"{eq.nombre} rechazó tu solicitud",
                  f"El capitán no aprobó tu ingreso a {eq.nombre}.", url='/cuenta/solicitudes/')
        except Exception:
            pass
        messages.info(request, f'Solicitud de {s.usuario.username} rechazada.')
    return redirect('cap_fichajes')


@login_required
def fichaje_cancelar(request, pk):
    eq = mi_equipo(request)
    s = get_object_or_404(SolicitudTraslado, pk=pk, equipo=eq, estado='pendiente')
    if request.method == 'POST':
        s.delete()
        messages.info(request, 'Solicitud cancelada.')
    return redirect('cap_fichajes')


@login_required
def cambiar_estado(request):
    """El capitán abre o cierra su propio equipo a nuevos jugadores."""
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    if request.method == 'POST':
        eq.abierto = not eq.abierto
        eq.save(update_fields=['abierto'])
        if eq.abierto:
            messages.success(request, f'{eq.nombre} está ABIERTO: acepta nuevos jugadores.')
        else:
            messages.warning(request, f'{eq.nombre} está CERRADO: nadie puede entrar por ahora.')
        return redirect('cap_fichajes')
    return redirect('cap_fichajes')


# ---------- ALINEACIONES ----------
@login_required
def alineaciones(request):
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    pendientes = Juego.objects.filter(Q(local=eq) | Q(visita=eq), estado__in=['programado', 'envivo']).order_by('fecha')
    # adjuntar si ya tiene alineación CON jugadores (las vacías no cuentan)
    alin_ids = set(Alineacion.objects.filter(
        equipo=eq, juego__in=pendientes, detalles__isnull=False,
    ).values_list('juego_id', flat=True))
    for j in pendientes:
        j.tiene_alin = j.id in alin_ids
    plantillas = PlantillaAlineacion.objects.filter(equipo=eq).prefetch_related('detalles__jugador')
    return render(request, 'capitanes/alineaciones.html', {
        'equipo': eq, 'pendientes': pendientes, 'plantillas': plantillas,
    })


@login_required
def alineacion_editar(request, juego_id):
    eq = mi_equipo(request)
    juego = get_object_or_404(Juego, pk=juego_id)
    if juego.local_id != eq.id and juego.visita_id != eq.id:
        messages.error(request, 'Ese juego no es de tu equipo.')
        return redirect('cap_alineaciones')
    alin, _ = Alineacion.objects.get_or_create(equipo=eq, juego=juego, defaults={'creada_por': request.user})
    roster = list(eq.jugadores.order_by('nombre'))
    detalles = {d.jugador_id: d for d in alin.detalles.select_related('jugador')}
    plantillas = PlantillaAlineacion.objects.filter(equipo=eq)

    if request.method == 'POST':
        acc = request.POST.get('accion', 'guardar')
        if acc == 'copiar_pareja':
            # Copia esta alineación al otro juego del día (ida <-> vuelta)
            from django.utils import timezone as _tz
            dia = _tz.localtime(juego.fecha).date()
            parejas = list(Juego.objects.filter(fecha__date=dia).filter(
                Q(local=juego.local, visita=juego.visita)
                | Q(local=juego.visita, visita=juego.local)
            ).exclude(pk=juego.pk))
            if not alin.detalles.exists():
                messages.error(request, 'Guarda primero la alineación de este juego antes de copiarla.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if not parejas:
                messages.info(request, 'No hay otro juego ida/vuelta ese día para copiar.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            n = 0
            for pj in parejas:
                dest, _ = Alineacion.objects.get_or_create(
                    equipo=eq, juego=pj, defaults={'creada_por': request.user})
                dest.detalles.all().delete()
                for d in alin.detalles.all():
                    if d.jugador.equipo_id == eq.id:
                        AlineacionDetalle.objects.create(
                            alineacion=dest, jugador=d.jugador,
                            posicion=d.posicion, orden_bateo=d.orden_bateo)
                        n += 1
                dest.creada_por = request.user
                dest.notas = (alin.notas or '')[:200]
                dest.pitcher_batea = alin.pitcher_batea
                dest.save()
            nombres = ', '.join(
                '%s vs %s %s' % (p.local, p.visita, p.fecha.strftime('%H:%M'))
                for p in parejas
            )
            messages.success(
                request, 'Alineación copiada al otro juego del día (%s).' % nombres)
            return redirect('cap_alin_editar', juego_id=juego.id)
        if acc == 'cargar_plantilla':
            pl = get_object_or_404(PlantillaAlineacion, pk=request.POST.get('plantilla'), equipo=eq)
            alin.detalles.all().delete()
            for d in pl.detalles.all():
                # solo si el jugador sigue en el equipo
                if d.jugador.equipo_id == eq.id:
                    AlineacionDetalle.objects.create(alineacion=alin, jugador=d.jugador, posicion=d.posicion, orden_bateo=d.orden_bateo)
            messages.success(request, f'Plantilla "{pl.nombre}" aplicada.')
            return redirect('cap_alin_editar', juego_id=juego.id)
        elif acc == 'guardar_plantilla':
            nombre = (request.POST.get('nombre_plantilla') or '').strip() or f"Plantilla {juego.local} vs {juego.visita}"
            pl = PlantillaAlineacion.objects.create(equipo=eq, nombre=nombre, creada_por=request.user)
            for d in alin.detalles.all():
                PlantillaDetalle.objects.create(plantilla=pl, jugador=d.jugador, posicion=d.posicion, orden_bateo=d.orden_bateo)
            messages.success(request, f'Plantilla "{nombre}" guardada con {alin.detalles.count()} jugadores.')
            return redirect('cap_alin_editar', juego_id=juego.id)
        else:
            # guardar alineación: listas jugador[], posicion[], orden[] — hasta 16 bateadores
            # (10 defensa + 1 designado BD + 5 asignados BA)
            jugs = request.POST.getlist('jugador')
            poss = request.POST.getlist('posicion')
            ords = request.POST.getlist('orden')
            # validaciones
            if not jugs:
                messages.error(request, 'Selecciona al menos 1 jugador.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if len(jugs) > 16:
                messages.error(request, 'Máximo 16 bateadores por juego (10 defensa + BD + 5 asignados).')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if len(set(jugs)) != len(jugs):
                messages.error(request, 'Hay jugadores repetidos.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            valid_pos = dict(ALIN_POSICIONES)
            for pos in poss:
                if pos not in valid_pos:
                    messages.error(request, f'Posición inválida: {pos}.')
                    return redirect('cap_alin_editar', juego_id=juego.id)
            # defensivas únicas; BD solo 1; BA hasta 5
            defens = [p for p in poss if p in POS_DEFENSIVAS]
            if len(set(defens)) != len(defens):
                messages.error(request, 'Hay posiciones defensivas repetidas. Cada una solo una vez.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if poss.count('BD') > 1:
                messages.error(request, 'Solo puede haber 1 bateador designado (BD).')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if poss.count('BA') > 5:
                messages.error(request, 'Máximo 5 bateadores asignados (BA).')
                return redirect('cap_alin_editar', juego_id=juego.id)
            try:
                ords_int = [int(o) for o in ords]
            except ValueError:
                messages.error(request, 'Orden al bate inválido.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if any(o < 1 or o > 16 for o in ords_int):
                messages.error(request, 'El orden al bate debe ser 1..16.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            if len(set(ords_int)) != len(ords_int):
                messages.error(request, 'Hay turnos al bate repetidos.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            pitcher_batea = bool(request.POST.get('pitcher_batea'))
            if pitcher_batea and 'P' not in poss:
                messages.error(request, 'Si el pitcher batea, marca quién lanza (P) o desactiva la opción.')
                return redirect('cap_alin_editar', juego_id=juego.id)
            alin.detalles.all().delete()
            for jid, pos, ordn in zip(jugs, poss, ords_int):
                jug = get_object_or_404(Jugador, pk=jid, equipo=eq)
                AlineacionDetalle.objects.create(alineacion=alin, jugador=jug, posicion=pos, orden_bateo=ordn)
            alin.creada_por = request.user
            alin.notas = request.POST.get('notas', '')[:200]
            alin.pitcher_batea = pitcher_batea
            alin.save()
            messages.success(request, f'Alineación guardada: {len(jugs)} jugadores.')
            return redirect('cap_alin_editar', juego_id=juego.id)

    # GET: ordenar detalles por orden_bateo
    detalles_list = list(alin.detalles.select_related('jugador').order_by('orden_bateo'))
    # mapa posicion -> detalle para pintar el terreno
    por_pos = {d.posicion: d for d in alin.detalles.select_related('jugador') if d.posicion in POS_DEFENSIVAS}
    # juego pareja ida/vuelta del mismo día (para botón copiar)
    from django.utils import timezone as _tz2
    try:
        dia2 = _tz2.localtime(juego.fecha).date()
        juego_pareja = list(Juego.objects.filter(fecha__date=dia2).filter(
            Q(local=juego.local, visita=juego.visita)
            | Q(local=juego.visita, visita=juego.local)
        ).exclude(pk=juego.pk).order_by('fecha'))
    except Exception:
        juego_pareja = []
    return render(request, 'capitanes/alineacion_editar.html', {
        'equipo': eq, 'juego': juego, 'alin': alin, 'roster': roster,
        'detalles': detalles, 'detalles_list': detalles_list, 'por_pos': por_pos,
        'plantillas': plantillas, 'posiciones': ALIN_POSICIONES,
        'juego_pareja': juego_pareja,
    })


@login_required
def plantilla_eliminar(request, pk):
    eq = mi_equipo(request)
    pl = get_object_or_404(PlantillaAlineacion, pk=pk, equipo=eq)
    if request.method == 'POST':
        pl.delete()
        messages.info(request, 'Plantilla eliminada.')
    return redirect('cap_alineaciones')


# ---------- TITULAR REGULAR (página pública) ----------
@login_required
def titular(request):
    """Alineación titular regular: 10 defensa + BD + 5 asignados.

    Es lo que se ve en la página pública del equipo.
    Separado de las alineaciones por juego.
    """
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    tit, _ = AlineacionTitular.objects.get_or_create(equipo=eq, defaults={'creada_por': request.user})
    roster = list(eq.jugadores.order_by('nombre'))

    if request.method == 'POST':
        jugs = request.POST.getlist('jugador')
        poss = request.POST.getlist('posicion')
        if len(jugs) != len(poss):
            messages.error(request, 'Datos incompletos.')
            return redirect('cap_titular')
        if len(jugs) > 16:
            messages.error(request, 'Máximo 16 en el titular (10 defensa + BD + 5 asignados).')
            return redirect('cap_titular')
        if len(set(jugs)) != len(jugs):
            messages.error(request, 'Hay jugadores repetidos.')
            return redirect('cap_titular')
        valid_pos = dict(TITULAR_POSICIONES)
        for pos in poss:
            if pos not in valid_pos:
                messages.error(request, f'Posición inválida: {pos}.')
                return redirect('cap_titular')
        if len(set(poss)) != len(poss):
            messages.error(request, 'Hay posiciones repetidas. Cada slot solo una vez.')
            return redirect('cap_titular')
        tit.detalles.all().delete()
        for jid, pos in zip(jugs, poss):
            jug = get_object_or_404(Jugador, pk=jid, equipo=eq)
            TitularDetalle.objects.create(titular=tit, jugador=jug, posicion=pos)
        tit.creada_por = request.user
        tit.save()
        messages.success(request, f'Titular guardado: {len(jugs)}/16. Ya se ve en la página pública.')
        return redirect('cap_titular')

    detalles_list = list(tit.detalles.select_related('jugador'))
    por_pos = {d.posicion: d.jugador for d in detalles_list}
    return render(request, 'capitanes/titular.html', {
        'equipo': eq, 'tit': tit, 'roster': roster,
        'detalles_list': detalles_list, 'por_pos': por_pos,
        'posiciones': POSICIONES,
    })


# ---------- MI EQUIPO (logo + portada) ----------
@login_required
def perfil_equipo(request):
    eq = mi_equipo(request)
    if not eq:
        messages.error(request, 'No tienes equipo asignado.')
        return redirect('cap_dash')
    if request.method == 'POST':
        if 'logo' in request.FILES:
            if eq.logo:
                eq.logo.delete(save=False)
            eq.logo = request.FILES['logo']
        if 'banner' in request.FILES:
            if eq.banner:
                eq.banner.delete(save=False)
            eq.banner = request.FILES['banner']
        if request.POST.get('quitar_logo') and not request.FILES.get('logo'):
            if eq.logo:
                eq.logo.delete(save=False)
            eq.logo = None
        if request.POST.get('quitar_banner') and not request.FILES.get('banner'):
            if eq.banner:
                eq.banner.delete(save=False)
            eq.banner = None
        color = (request.POST.get('color') or '').strip()
        if color:
            eq.color = color[:20]
        # Encuadre del banner (0-100, con tolerancia a valores maliciosos)
        try:
            eq.banner_x = min(100, max(0, int(request.POST.get('banner_x', eq.banner_x))))
        except Exception:
            pass
        try:
            eq.banner_y = min(100, max(0, int(request.POST.get('banner_y', eq.banner_y))))
        except Exception:
            pass
        try:
            eq.full_clean(exclude=['nombre', 'sigla', 'capitan'])
            eq.save()
            messages.success(request, 'Imagen del equipo actualizada.')
        except Exception as e:
            messages.error(request, f'No se pudo guardar: {e}.')
        return redirect('cap_perfil')
    return render(request, 'capitanes/perfil_equipo.html', {'equipo': eq})
