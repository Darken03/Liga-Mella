from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from torneos.models import Juego, Jugada, Entrada
from equipos.models import Jugador
from estadisticas.models import ActuacionBateo, ActuacionPitcheo

RESULTADOS_OUT = {'out', 'k', 'sf', 'fc'}
RESULTADOS_HIT = {'hit', 'doble', 'triple', 'hr'}


def _lineup(juego, equipo):
    """Orden de bateo: Alineación del juego si existe, si no roster por dorsal."""
    try:
        from capitanes.models import Alineacion
        alin = Alineacion.objects.filter(juego=juego, equipo=equipo).prefetch_related('detalles__jugador').first()
        if alin and alin.detalles.exists():
            return list(alin.orden_bateo())
    except Exception:
        pass
    # fallback: roster
    roster = list(equipo.jugadores.order_by('dorsal'))
    class _D:
        def __init__(self, j, i):
            self.jugador = j; self.jugador_id = j.id; self.posicion = j.posicion; self.orden_bateo = i + 1
    return [_D(j, i) for i, j in enumerate(roster)]


def _ensure_pitcher(juego, equipo_defiende):
    """Devuelve pitcher actual del equipo que defiende, auto-asignando si falta."""
    attr = 'pitcher_local' if equipo_defiende.id == juego.local_id else 'pitcher_visita'
    pj = getattr(juego, attr)
    if pj and pj.equipo_id == equipo_defiende.id:
        return pj
    # busca P en alineación, si no abridor
    try:
        from capitanes.models import Alineacion
        alin = Alineacion.objects.filter(juego=juego, equipo=equipo_defiende).first()
        if alin:
            d = alin.detalles.filter(posicion='P').select_related('jugador').first()
            if d:
                setattr(juego, attr, d.jugador); juego.save(update_fields=[attr])
                return d.jugador
    except Exception:
        pass
    ab = equipo_defiende.abridor
    if ab:
        setattr(juego, attr, ab); juego.save(update_fields=[attr])
    return ab


def _get_entrada(juego, numero):
    e, _ = Entrada.objects.get_or_create(juego=juego, numero=numero)
    return e


def _alineacion_de(juego, equipo):
    """Alineación con jugadores para cambios del anotador (no crea vacías)."""
    from capitanes.models import Alineacion
    return (Alineacion.objects
            .filter(juego=juego, equipo=equipo)
            .prefetch_related('detalles__jugador').first())


def _sync_pitcher_equipo(juego, equipo):
    """Si el lineup tiene un P, ese es el pitcher; si no, se deja el actual."""
    alin = _alineacion_de(juego, equipo)
    if not alin:
        return
    d = alin.detalles.filter(posicion='P').select_related('jugador').first()
    if not d:
        return
    attr = 'pitcher_local' if equipo.id == juego.local_id else 'pitcher_visita'
    if getattr(juego, attr + '_id') != d.jugador_id:
        setattr(juego, attr, d.jugador)
        juego.save(update_fields=[attr])


def _resumen_juego(juego):
    """Stats por bateador en ESTE juego desde Jugadas detalladas."""
    from collections import defaultdict
    res = defaultdict(lambda: {'ab': 0, 'h': 0, 'hr': 0, 'rbi': 0, 'r': 0, 'bb': 0, 'k': 0, 'pa': []})
    for t in juego.jugadas.filter(bateador__isnull=False).order_by('id'):
        r = res[t.bateador_id]
        r['ab'] += t.d_ab; r['h'] += t.d_h; r['hr'] += t.d_hr
        r['rbi'] += t.d_rbi; r['r'] += t.d_r; r['bb'] += t.d_bb
        if t.resultado == 'k':
            r['k'] += 1
        r['pa'].append({'inn': t.inning_num, 'mitad': t.mitad, 'res': t.resultado, 'rbi': t.rbi})
    return res


def _estado(juego):
    juego.refresh_from_db()
    max_inn = max(7, juego.inning_num)
    entradas = []
    for n in range(1, max_inn + 1):
        e = juego.entradas.filter(numero=n).first()
        entradas.append({'n': n, 'cl': e.carreras_local if e else 0, 'cv': e.carreras_visita if e else 0,
                         'hl': e.hits_local if e else 0, 'hv': e.hits_visita if e else 0})
    tot_hl = sum(x['hl'] for x in entradas); tot_hv = sum(x['hv'] for x in entradas)
    lin_l = _lineup(juego, juego.local); lin_v = _lineup(juego, juego.visita)
    resumen = _resumen_juego(juego)
    def ser_lin(lin, idx):
        out = []
        for i, d in enumerate(lin):
            j = d.jugador
            s = resumen.get(j.id, {'ab': 0, 'h': 0, 'hr': 0, 'rbi': 0, 'r': 0, 'bb': 0, 'k': 0})
            out.append({'id': j.id, 'nombre': j.nombre_completo, 'dorsal': j.dorsal, 'pos': d.posicion,
                        'orden': d.orden_bateo, 'actual': (i == (idx % len(lin)) if lin else False),
                        'ab': s['ab'], 'h': s['h'], 'hr': s['hr'], 'rbi': s['rbi'], 'r': s['r'], 'bb': s['bb'], 'k': s['k']})
        return out
    batea_local = (juego.mitad == 'baja')
    idx = juego.idx_local if batea_local else juego.idx_visita
    lin_act = lin_l if batea_local else lin_v
    bateador_actual = None
    if lin_act:
        d = lin_act[idx % len(lin_act)]
        bateador_actual = {'id': d.jugador.id, 'nombre': d.jugador.nombre_completo, 'dorsal': d.jugador.dorsal, 'pos': d.posicion, 'orden': d.orden_bateo}
    pdef = juego.equipo_defiende
    pitcher = _ensure_pitcher(juego, pdef) if juego.estado != 'final' else getattr(juego, 'pitcher_local' if pdef.id == juego.local_id else 'pitcher_visita')
    ros_l = [{'id': j.id, 'nombre': j.nombre_completo, 'dorsal': j.dorsal} for j in juego.local.jugadores.order_by('dorsal')]
    ros_v = [{'id': j.id, 'nombre': j.nombre_completo, 'dorsal': j.dorsal} for j in juego.visita.jugadores.order_by('dorsal')]
    ids_l = {d.jugador_id for d in lin_l}; ids_v = {d.jugador_id for d in lin_v}
    def ser_banca(equipo, ids):
        return [{'id': j.id, 'nombre': j.nombre_completo, 'dorsal': j.dorsal, 'pos_base': j.posicion}
                for j in equipo.jugadores.order_by('dorsal') if j.id not in ids]
    cambios_qs = getattr(juego, 'cambios', None)
    if cambios_qs is not None:
        cambios = [{'id': c.id, 'tipo': c.tipo,
                    'txt': str(c), 'inn': f"{c.inning_num}RA {'ALTA' if c.mitad == 'alta' else 'BAJA'}"}
                   for c in cambios_qs.select_related('sale', 'entra').order_by('-id')[:6]]
    else:
        cambios = []
    return {
        'juego': {'id': juego.id, 'estado': juego.estado, 'cl': juego.carreras_local, 'cv': juego.carreras_visita,
                  'inning_num': juego.inning_num, 'mitad': juego.mitad, 'inning_txt': juego.inning_actual,
                  'outs': juego.outs, 'bolas': juego.bolas, 'strikes': juego.strikes,
                  'local': {'id': juego.local.id, 'nombre': juego.local.nombre, 'sigla': juego.local.sigla, 'color': juego.local.color},
                  'visita': {'id': juego.visita.id, 'nombre': juego.visita.nombre, 'sigla': juego.visita.sigla, 'color': juego.visita.color},
                  'batea': 'local' if batea_local else 'visita',
                  'torneo': juego.torneo.nombre if juego.torneo_id else ''},
        'entradas': entradas, 'tot_hl': tot_hl, 'tot_hv': tot_hv,
        'lineup_local': ser_lin(lin_l, juego.idx_local), 'lineup_visita': ser_lin(lin_v, juego.idx_visita),
        'bateador_actual': bateador_actual,
        'pitcher': {'id': pitcher.id, 'nombre': pitcher.nombre_completo, 'equipo': pdef.nombre} if pitcher else None,
        'roster_local': ros_l, 'roster_visita': ros_v,
        'banca_local': ser_banca(juego.local, ids_l), 'banca_visita': ser_banca(juego.visita, ids_v),
        'cambios': cambios,
        'ultimas': [{'id': x.id, 'txt': x.descripcion, 'inn': x.inning} for x in juego.jugadas.order_by('-id')[:8]],
    }


@login_required
def lista(request):
    from datetime import datetime
    hoy = timezone.localdate()
    dias = sorted({timezone.localtime(j.fecha).date() for j in Juego.objects.all()})
    sel = request.GET.get('d', '')
    try:
        sel = datetime.strptime(sel, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        sel = None
    if sel is None or (dias and sel not in dias):
        fut = [d for d in dias if d >= hoy]
        sel = fut[0] if fut else (dias[-1] if dias else hoy)
    ant = [d for d in dias if d < sel]
    sig = [d for d in dias if d > sel]
    dom_ant = ant[-1] if ant else None
    dom_sig = sig[0] if sig else None
    juegos_dia = list(Juego.objects.filter(fecha__date=sel).select_related('local', 'visita', 'torneo').order_by('fecha'))
    # etiquetas ida/vuelta por pareja del día
    vistos = {}
    for j in juegos_dia:
        key = tuple(sorted((j.local_id, j.visita_id)))
        n = vistos.get(key, 0) + 1
        vistos[key] = n
        j.n_serie = n
        primero = [x for x in juegos_dia if tuple(sorted((x.local_id, x.visita_id))) == key][0]
        j.es_ida = (j.local_id == primero.local_id and j.visita_id == primero.visita_id)
    envivo = list(Juego.objects.filter(estado='envivo').select_related('local', 'visita', 'torneo').order_by('fecha'))
    return render(request, 'anotador/lista.html', {
        'juegos_dia': juegos_dia, 'hoy': hoy, 'sel': sel,
        'dom_ant': dom_ant, 'dom_sig': dom_sig, 'dias': dias,
        'nj': dias.index(sel) + 1 if sel in dias else None,
        'envivo': envivo,
    })


@login_required
def anotar(request, pk):
    juego = get_object_or_404(Juego.objects.select_related('local', 'visita', 'torneo'), pk=pk)
    # pitchers por defecto para mostrar selectores
    _ensure_pitcher(juego, juego.local); _ensure_pitcher(juego, juego.visita)
    ctx = _estado(juego)
    ctx['juego_obj'] = juego
    return render(request, 'anotador/anotar.html', ctx)


@login_required
def api_estado(request, pk):
    juego = get_object_or_404(Juego, pk=pk)
    return JsonResponse(_estado(juego))


def _deltas(resultado, rbi, anoto):
    d = dict(ab=0, h=0, h2=0, h3=0, hr=0, r=0, rbi=rbi, bb=0, hbp=0, sf=0, kbat=0, kpit=0, es_out=False, es_hit=False)
    if resultado == 'hit': d.update(ab=1, h=1, es_hit=True)
    elif resultado == 'doble': d.update(ab=1, h=1, h2=1, es_hit=True)
    elif resultado == 'triple': d.update(ab=1, h=1, h3=1, es_hit=True)
    elif resultado == 'hr': d.update(ab=1, h=1, hr=1, r=1, es_hit=True)
    elif resultado == 'out': d.update(ab=1, es_out=True)
    elif resultado == 'fc': d.update(ab=1, es_out=True)
    elif resultado == 'k': d.update(ab=1, kbat=1, kpit=1, es_out=True)
    elif resultado == 'bb': d.update(bb=1)
    elif resultado == 'hbp': d.update(hbp=1)
    elif resultado == 'sf': d.update(sf=1, es_out=True)
    elif resultado == 'error': d.update(ab=1, es_out=False)
    if anoto and resultado != 'hr':
        d['r'] = 1
    return d


@login_required
@transaction.atomic
def api_turno(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requerido'}, status=405)
    import json
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    juego = get_object_or_404(Juego.objects.select_related('local', 'visita', 'torneo'), pk=pk)
    if juego.estado == 'final':
        return JsonResponse({'ok': False, 'error': 'Juego finalizado'}, status=400)
    bateador_id = data.get('bateador_id')
    resultado = (data.get('resultado') or '').strip()
    try:
        rbi = max(0, min(6, int(data.get('rbi') or 0)))
        carreras = max(0, min(6, int(data.get('carreras') or 0)))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'CI/carreras inválidas'}, status=400)
    anoto = bool(data.get('anoto'))
    if resultado not in ('hit', 'doble', 'triple', 'hr', 'out', 'k', 'bb', 'hbp', 'sf', 'error', 'fc'):
        return JsonResponse({'ok': False, 'error': 'Resultado inválido'}, status=400)
    if resultado == 'hr' and rbi < 1:
        rbi = 1
    if resultado == 'hr' and carreras < 1:
        carreras = max(carreras, 1)
    eq_batea = juego.equipo_batea
    lin = _lineup(juego, eq_batea)
    if not lin:
        return JsonResponse({'ok': False, 'error': 'Sin lineup: el capitán debe alinear.'}, status=400)
    ids = [d.jugador_id for d in lin]
    s_idx = juego.idx_local if eq_batea.id == juego.local_id else juego.idx_visita
    esperado = lin[s_idx % len(lin)]
    bateador_id = data.get('bateador_id')
    if bateador_id:
        # orden obligatorio: solo acepta al bateador que le toca
        try:
            if int(bateador_id) != esperado.jugador_id:
                return JsonResponse({'ok': False, 'error': f"Le toca a {esperado.jugador.nombre_completo} (orden {esperado.orden_bateo})."}, status=400)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Bateador inválido'}, status=400)
    bateador = esperado.jugador
    pos = s_idx % len(lin)
    prev_bolas, prev_strikes, prev_outs = juego.bolas, juego.strikes, juego.outs
    prev_inn, prev_mit = juego.inning_num, juego.mitad
    s_cl, s_cv = juego.carreras_local, juego.carreras_visita
    dlt = _deltas(resultado, rbi, anoto)
    pitcher = _ensure_pitcher(juego, juego.equipo_defiende)
    # 1) stats bateo
    linea, _ = ActuacionBateo.objects.get_or_create(jugador=bateador, torneo=juego.torneo)
    linea.ab += dlt['ab']; linea.h += dlt['h']; linea.h2 += dlt['h2']; linea.h3 += dlt['h3']
    linea.hr += dlt['hr']; linea.r += dlt['r']; linea.rbi += dlt['rbi']
    linea.bb += dlt['bb']; linea.hbp += dlt['hbp']; linea.sf += dlt['sf']; linea.k += dlt['kbat']
    linea.save()
    bateador.hr += dlt['hr']; bateador.rbi += dlt['rbi']; bateador.avg = linea.avg; bateador.save(update_fields=['hr', 'rbi', 'avg'])
    # 2) stats pitcher (K automático + IP)
    if pitcher and pitcher.equipo_id != eq_batea.id:
        pl, _ = ActuacionPitcheo.objects.get_or_create(jugador=pitcher, torneo=juego.torneo)
        if pl.jl == 0: pl.jl = 1
        pl.k += dlt['kpit']
        if resultado == 'bb' or resultado == 'hbp': pl.bb += 1
        if dlt['es_hit']: pl.h += 1
        if carreras: pl.r += carreras; pl.er += carreras
        if dlt['es_out']: pl.ip_outs += 1
        pl.save()
    # 3) marcador + entrada
    ent = _get_entrada(juego, juego.inning_num)
    es_local_batea = (eq_batea.id == juego.local_id)
    if es_local_batea:
        juego.carreras_local += carreras; ent.carreras_local += carreras
        if dlt['es_hit']: ent.hits_local += 1; juego.save(update_fields=['carreras_local'])
        else: juego.save(update_fields=['carreras_local'])
    else:
        juego.carreras_visita += carreras; ent.carreras_visita += carreras
        if dlt['es_hit']: ent.hits_visita += 1; juego.save(update_fields=['carreras_visita'])
        else: juego.save(update_fields=['carreras_visita'])
    ent.save()
    # 4) conteo / outs / inning
    if dlt['es_out']:
        juego.outs += 1
    juego.bolas = 0; juego.strikes = 0
    cambio = False
    if juego.outs >= 3:
        juego.outs = 0
        cambio = True
        if juego.mitad == 'alta':
            juego.mitad = 'baja'
        else:
            juego.mitad = 'alta'; juego.inning_num += 1
            _get_entrada(juego, juego.inning_num)
    # 5) avanza turno
    if lin:
        nxt = ((pos + 1) if pos is not None else (s_idx + 1)) % len(lin)
        if es_local_batea: juego.idx_local = nxt
        else: juego.idx_visita = nxt
    juego.sync_inning_txt(); juego.save()
    # 6) jugada (con snapshot previo real)
    jug = Jugada.objects.create(
        juego=juego, inning=f"{prev_inn}RA {'ALTA' if prev_mit == 'alta' else 'BAJA'}", inning_num=prev_inn,
        mitad=prev_mit, descripcion=f"{bateador.nombre_completo} #{bateador.dorsal}: {resultado.upper()} (+{rbi} CI, +{carreras} C)",
        tipo='hit' if dlt['es_hit'] else ('out' if dlt['es_out'] else ('bb' if resultado in ('bb', 'hbp') else ('hr' if resultado == 'hr' else 'otro'))),
        bateador=bateador, pitcher=pitcher, equipo_batea=eq_batea, resultado=resultado, rbi=rbi, carreras=carreras,
        d_ab=dlt['ab'], d_h=dlt['h'], d_h2=dlt['h2'], d_h3=dlt['h3'], d_hr=dlt['hr'], d_r=dlt['r'], d_rbi=dlt['rbi'],
        d_bb=dlt['bb'], d_hbp=dlt['hbp'], d_sf=dlt['sf'], d_kpit=dlt['kpit'],
        s_outs=prev_outs, s_bolas=prev_bolas, s_strikes=prev_strikes,
        s_inning=prev_inn, s_mitad=prev_mit, s_idx=s_idx, s_cl=s_cl, s_cv=s_cv,
    )
    if juego.estado == 'programado':
        juego.estado = 'envivo'; juego.save(update_fields=['estado'])
    return JsonResponse({'ok': True, 'state': _estado(juego), 'cambio_inning': cambio})


@login_required
@transaction.atomic
def api_control(request, pk):
    import json
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    juego = get_object_or_404(Juego, pk=pk)
    acc = data.get('accion')
    if acc == 'iniciar':
        juego.estado = 'envivo'; juego.save(update_fields=['estado'])
    elif acc == 'finalizar':
        if juego.estado != 'final':
            juego.estado = 'final'; juego.save(update_fields=['estado'])
            from torneos.models import finalizar_juego
            finalizar_juego(juego)
    elif acc == 'bola':
        juego.bolas += 1
        auto_bb = False
        if juego.bolas >= 4:
            juego.bolas = 0; juego.strikes = 0; auto_bb = True
        juego.save()
        st = _estado(juego); st['auto_bb'] = auto_bb
        return JsonResponse({'ok': True, 'state': st})
    elif acc == 'strike':
        juego.strikes += 1
        auto_k = False
        if juego.strikes >= 3:
            juego.strikes = 0; juego.bolas = 0; auto_k = True
        juego.save()
        st = _estado(juego); st['auto_k'] = auto_k
        return JsonResponse({'ok': True, 'state': st})
    elif acc == 'out_manual':
        juego.outs += 1
        if juego.outs >= 3:
            juego.outs = 0
            if juego.mitad == 'alta': juego.mitad = 'baja'
            else: juego.mitad = 'alta'; juego.inning_num += 1
            _get_entrada(juego, juego.inning_num)
        juego.bolas = 0; juego.strikes = 0; juego.sync_inning_txt(); juego.save()
    elif acc == 'reset_count':
        juego.bolas = 0; juego.strikes = 0; juego.save()
    elif acc == 'cambiar_mitad':
        juego.mitad = 'baja' if juego.mitad == 'alta' else 'alta'
        juego.outs = 0; juego.bolas = 0; juego.strikes = 0; juego.sync_inning_txt(); juego.save()
    elif acc == 'mas_inning':
        juego.inning_num += 1; _get_entrada(juego, juego.inning_num); juego.sync_inning_txt(); juego.save()
    elif acc == 'menos_inning':
        if juego.inning_num > 1: juego.inning_num -= 1; juego.sync_inning_txt(); juego.save()
    elif acc == 'carrera_local':
        juego.carreras_local += 1; _get_entrada(juego, juego.inning_num).save()
        e = _get_entrada(juego, juego.inning_num); e.carreras_local += 1; e.save(); juego.save()
    elif acc == 'carrera_visita':
        e = _get_entrada(juego, juego.inning_num); e.carreras_visita += 1; e.save()
        juego.carreras_visita += 1; juego.save()
    elif acc == 'quitar_carrera_local':
        if juego.carreras_local > 0: juego.carreras_local -= 1; juego.save()
        e = juego.entradas.filter(numero=juego.inning_num).first()
        if e and e.carreras_local > 0: e.carreras_local -= 1; e.save()
    elif acc == 'quitar_carrera_visita':
        if juego.carreras_visita > 0: juego.carreras_visita -= 1; juego.save()
        e = juego.entradas.filter(numero=juego.inning_num).first()
        if e and e.carreras_visita > 0: e.carreras_visita -= 1; e.save()
    else:
        return JsonResponse({'ok': False, 'error': 'Acción inválida'}, status=400)
    return JsonResponse({'ok': True, 'state': _estado(juego)})


@login_required
@transaction.atomic
def api_cambio(request, pk):
    """Registra sustituciones y swaps defensivos en el lineup del juego.

    Acciones:
    - sustituir: {equipo_id, sale_id, entra_id, posicion?}
      El que entra hereda el orden al bate del que sale. Si el que entra
      ya estaba en el lineup, se intercambian los jugadores entre los dos
      órdenes (las posiciones de cada orden se conservan, salvo `posicion`).
    - swap_pos: {equipo_id, jugador_a_id, jugador_b_id? , posicion?}
      Intercambia posiciones sin tocar el orden al bate, o asigna una
      posición directa a un jugador.
    """
    import json
    from capitanes.models import ALIN_POSICIONES
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requerido'}, status=405)
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    juego = get_object_or_404(Juego.objects.select_related('local', 'visita', 'torneo'), pk=pk)
    if juego.estado == 'final':
        return JsonResponse({'ok': False, 'error': 'Juego finalizado'}, status=400)
    from anotador.models import Sustitucion
    acc = (data.get('accion') or '').strip()
    POS_OK = {c for c, _ in ALIN_POSICIONES}

    def _equipo(eid):
        try:
            eid = int(eid)
        except (TypeError, ValueError):
            return None
        if eid == juego.local_id:
            return juego.local
        if eid == juego.visita_id:
            return juego.visita
        return None

    def _snap(equipo):
        s_idx = juego.idx_local if equipo.id == juego.local_id else juego.idx_visita
        return (s_idx, juego.inning_num, juego.mitad, juego.outs,
                juego.bolas, juego.strikes, juego.carreras_local, juego.carreras_visita)

    def _jug_cambio(equipo, descripcion, s_idx, s_cl, s_cv,
                    s_outs, s_bolas, s_strikes, s_inn, s_mit):
        inn_txt = f"{s_inn}RA {'ALTA' if s_mit == 'alta' else 'BAJA'}"
        return Jugada.objects.create(
            juego=juego, inning=inn_txt, inning_num=s_inn, mitad=s_mit,
            descripcion=descripcion[:200], tipo='cambio',
            equipo_batea=equipo, resultado='otro', rbi=0, carreras=0,
            s_outs=s_outs, s_bolas=s_bolas, s_strikes=s_strikes,
            s_inning=s_inn, s_mitad=s_mit, s_idx=s_idx, s_cl=s_cl, s_cv=s_cv,
        )

    if acc == 'sustituir':
        equipo = _equipo(data.get('equipo_id'))
        if not equipo:
            return JsonResponse({'ok': False, 'error': 'Equipo inválido'}, status=400)
        try:
            sale_id, entra_id = int(data.get('sale_id')), int(data.get('entra_id'))
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'sale_id / entra_id inválidos'}, status=400)
        if sale_id == entra_id:
            return JsonResponse({'ok': False, 'error': 'Son el mismo jugador'}, status=400)
        pos_new_raw = (data.get('posicion') or '').strip().upper()
        if pos_new_raw and pos_new_raw not in POS_OK:
            return JsonResponse({'ok': False, 'error': 'Posición inválida'}, status=400)
        sale = Jugador.objects.filter(pk=sale_id, equipo=equipo).first()
        entra = Jugador.objects.filter(pk=entra_id, equipo=equipo).first()
        if not sale or not entra:
            return JsonResponse({'ok': False, 'error': 'Los jugadores deben ser del mismo equipo'}, status=400)
        alin = _alineacion_de(juego, equipo)
        if not alin or not alin.detalles.exists():
            return JsonResponse({'ok': False, 'error': 'Sin lineup: el capitán debe alinear.'}, status=400)
        det_sale = alin.detalles.filter(jugador_id=sale_id).first()
        if not det_sale:
            return JsonResponse({'ok': False, 'error': f'{sale.nombre_completo} no está en el lineup.'}, status=400)
        det_entra = alin.detalles.filter(jugador_id=entra_id).first()
        s_idx, s_inn, s_mit, s_outs, s_bolas, s_strikes, s_cl, s_cv = _snap(equipo)
        orden_sale = det_sale.orden_bateo
        pos_sale_old = det_sale.posicion
        if det_entra is None:
            # caso banca: entra ocupa el orden del que sale
            pos_nueva = pos_new_raw or pos_sale_old
            det_sale.jugador = entra
            det_sale.posicion = pos_nueva
            det_sale.save()
            desc = (f"🔄 Cambio {equipo.sigla}: sale {sale.nombre_completo} #{sale.dorsal} "
                    f"entra {entra.nombre_completo} #{entra.dorsal} en {orden_sale}° ({pos_sale_old}→{pos_nueva})")
            jug = _jug_cambio(equipo, desc, s_idx, s_cl, s_cv, s_outs, s_bolas, s_strikes, s_inn, s_mit)
            Sustitucion.objects.create(juego=juego, equipo=equipo, jugada=jug, tipo='sustitucion',
                                       sale=sale, entra=entra, orden_sale=orden_sale, orden_entra=None,
                                       pos_sale_old=pos_sale_old, pos_sale_new=pos_nueva,
                                       inning_num=s_inn, mitad=s_mit, s_idx=s_idx)
        else:
            # ambos en lineup: intercambian jugadores, cada orden conserva su posición
            orden_entra = det_entra.orden_bateo
            pos_entra_old = det_entra.posicion
            pos_entra_new = pos_new_raw or pos_sale_old
            # evita el unique (alineacion, jugador): borra y recrea cruzados
            pos_s = pos_entra_new  # lo que tendrá el orden_sale
            pos_e = pos_entra_old  # el orden_entra conserva su posición
            det_sale.delete()
            det_entra.delete()
            alin.detalles.create(jugador=entra, posicion=pos_s, orden_bateo=orden_sale)
            alin.detalles.create(jugador=sale, posicion=pos_e, orden_bateo=orden_entra)
            desc = (f"🔄 Swap {equipo.sigla}: {sale.nombre_completo} ({orden_sale}°) x "
                    f"{entra.nombre_completo} ({orden_entra}°)")
            jug = _jug_cambio(equipo, desc, s_idx, s_cl, s_cv, s_outs, s_bolas, s_strikes, s_inn, s_mit)
            Sustitucion.objects.create(juego=juego, equipo=equipo, jugada=jug, tipo='sustitucion',
                                       sale=sale, entra=entra, orden_sale=orden_sale, orden_entra=orden_entra,
                                       pos_sale_old=pos_sale_old, pos_sale_new=pos_s,
                                       pos_entra_old=pos_entra_old, pos_entra_new=pos_e,
                                       inning_num=s_inn, mitad=s_mit, s_idx=s_idx)
        _sync_pitcher_equipo(juego, equipo)
        return JsonResponse({'ok': True, 'state': _estado(juego)})

    if acc == 'swap_pos':
        equipo = _equipo(data.get('equipo_id'))
        if not equipo:
            return JsonResponse({'ok': False, 'error': 'Equipo inválido'}, status=400)
        try:
            a_id = int(data.get('jugador_a_id'))
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'jugador_a inválido'}, status=400)
        b_raw = data.get('jugador_b_id')
        try:
            b_id = int(b_raw) if b_raw else None
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'jugador_b inválido'}, status=400)
        pos_raw = (data.get('posicion') or '').strip().upper()
        if pos_raw and pos_raw not in POS_OK:
            return JsonResponse({'ok': False, 'error': 'Posición inválida'}, status=400)
        alin = _alineacion_de(juego, equipo)
        if not alin or not alin.detalles.exists():
            return JsonResponse({'ok': False, 'error': 'Sin lineup: el capitán debe alinear.'}, status=400)
        det_a = alin.detalles.select_related('jugador').filter(jugador_id=a_id).first()
        if not det_a:
            return JsonResponse({'ok': False, 'error': 'El jugador A no está en el lineup.'}, status=400)
        s_idx, s_inn, s_mit, s_outs, s_bolas, s_strikes, s_cl, s_cv = _snap(equipo)
        if b_id:
            if b_id == a_id:
                return JsonResponse({'ok': False, 'error': 'Son el mismo jugador'}, status=400)
            det_b = alin.detalles.select_related('jugador').filter(jugador_id=b_id).first()
            if not det_b:
                return JsonResponse({'ok': False, 'error': 'El jugador B no está en el lineup.'}, status=400)
            pa, pb = det_a.posicion, det_b.posicion
            det_a.posicion, det_b.posicion = pb, pa
            det_a.save(update_fields=['posicion'])
            det_b.save(update_fields=['posicion'])
            desc = (f"🔄 Swap defensivo {equipo.sigla}: {det_a.jugador.nombre_completo} ({pa}→{pb}) x "
                    f"{det_b.jugador.nombre_completo} ({pb}→{pa})")
            jug = _jug_cambio(equipo, desc, s_idx, s_cl, s_cv, s_outs, s_bolas, s_strikes, s_inn, s_mit)
            Sustitucion.objects.create(juego=juego, equipo=equipo, jugada=jug, tipo='swap_pos',
                                       sale=det_a.jugador, entra=det_b.jugador,
                                       orden_sale=det_a.orden_bateo, orden_entra=det_b.orden_bateo,
                                       pos_sale_old=pa, pos_sale_new=pb,
                                       pos_entra_old=pb, pos_entra_new=pa,
                                       inning_num=s_inn, mitad=s_mit, s_idx=s_idx)
        elif pos_raw:
            pa = det_a.posicion
            if pa == pos_raw:
                return JsonResponse({'ok': False, 'error': 'Ya juega ahí'}, status=400)
            det_a.posicion = pos_raw
            det_a.save(update_fields=['posicion'])
            desc = (f"🔄 Cambio defensivo {equipo.sigla}: {det_a.jugador.nombre_completo} {pa}→{pos_raw} ({det_a.orden_bateo}°)")
            jug = _jug_cambio(equipo, desc, s_idx, s_cl, s_cv, s_outs, s_bolas, s_strikes, s_inn, s_mit)
            Sustitucion.objects.create(juego=juego, equipo=equipo, jugada=jug, tipo='swap_pos',
                                       sale=det_a.jugador, entra=None,
                                       orden_sale=det_a.orden_bateo, orden_entra=None,
                                       pos_sale_old=pa, pos_sale_new=pos_raw,
                                       inning_num=s_inn, mitad=s_mit, s_idx=s_idx)
        else:
            return JsonResponse({'ok': False, 'error': 'Indica jugador B o una posición'}, status=400)
        _sync_pitcher_equipo(juego, equipo)
        return JsonResponse({'ok': True, 'state': _estado(juego)})

    return JsonResponse({'ok': False, 'error': 'Acción inválida'}, status=400)


@login_required
@transaction.atomic
def api_deshacer(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requerido'}, status=405)
    juego = get_object_or_404(Juego.objects.select_related('torneo'), pk=pk)
    if juego.estado == 'final':
        return JsonResponse({'ok': False, 'error': 'Juego finalizado, no se puede deshacer'}, status=400)
    jug = juego.jugadas.order_by('-id').first()
    if not jug:
        return JsonResponse({'ok': False, 'error': 'Nada que deshacer'}, status=400)
    # --- deshacer un cambio (sustitución / swap): revierte el lineup ---
    if jug.tipo == 'cambio':
        from anotador.models import Sustitucion
        try:
            sus = jug.sustitucion
        except Sustitucion.DoesNotExist:
            sus = None
        if sus is not None:
            alin = _alineacion_de(juego, sus.equipo)
            if alin:
                if sus.tipo == 'sustitucion' and sus.orden_entra is None:
                    det = alin.detalles.filter(orden_bateo=sus.orden_sale).first()
                    if det and sus.sale_id:
                        det.jugador = sus.sale
                        det.posicion = sus.pos_sale_old or det.posicion
                        det.save()
                elif sus.tipo == 'sustitucion' and sus.orden_entra is not None:
                    ds = alin.detalles.filter(orden_bateo=sus.orden_sale).first()
                    de = alin.detalles.filter(orden_bateo=sus.orden_entra).first()
                    if ds and de and sus.sale_id and sus.entra_id:
                        # revierte el swap borrando y recreando (evita unique)
                        ps_old, pe_old = sus.pos_sale_old, sus.pos_entra_old
                        ds.delete()
                        de.delete()
                        alin.detalles.create(jugador=sus.sale, posicion=ps_old or '1B', orden_bateo=sus.orden_sale)
                        alin.detalles.create(jugador=sus.entra, posicion=pe_old or '1B', orden_bateo=sus.orden_entra)
                elif sus.tipo == 'swap_pos':
                    if sus.orden_entra is not None:
                        ds = alin.detalles.filter(orden_bateo=sus.orden_sale).first()
                        de = alin.detalles.filter(orden_bateo=sus.orden_entra).first()
                        if ds:
                            ds.posicion = sus.pos_sale_old or ds.posicion
                            ds.save(update_fields=['posicion'])
                        if de:
                            de.posicion = sus.pos_entra_old or de.posicion
                            de.save(update_fields=['posicion'])
                    else:
                        ds = alin.detalles.filter(orden_bateo=sus.orden_sale).first()
                        if ds:
                            ds.posicion = sus.pos_sale_old or ds.posicion
                            ds.save(update_fields=['posicion'])
                # restaura el índice del equipo cambiado y el pitcher
                if sus.equipo_id == juego.local_id:
                    juego.idx_local = sus.s_idx
                elif sus.equipo_id == juego.visita_id:
                    juego.idx_visita = sus.s_idx
                juego.save(update_fields=['idx_local', 'idx_visita'])
                _sync_pitcher_equipo(juego, sus.equipo)
            txt = jug.descripcion
            jug.delete()  # borra en cascada la Sustitucion
            return JsonResponse({'ok': True, 'state': _estado(juego), 'deshecho': txt})
        # cambio viejo sin registro: solo borra la jugada
        txt = jug.descripcion
        jug.delete()
        return JsonResponse({'ok': True, 'state': _estado(juego), 'deshecho': txt})
    if jug.bateador_id is None:
        txt = jug.descripcion
        jug.delete()
        return JsonResponse({'ok': True, 'state': _estado(juego), 'deshecho': txt})
    # revierte stats bateo
    if jug.bateador:
        lin = ActuacionBateo.objects.filter(jugador=jug.bateador, torneo=juego.torneo).first()
        if lin:
            lin.ab = max(0, lin.ab - jug.d_ab); lin.h = max(0, lin.h - jug.d_h)
            lin.h2 = max(0, lin.h2 - jug.d_h2); lin.h3 = max(0, lin.h3 - jug.d_h3)
            lin.hr = max(0, lin.hr - jug.d_hr); lin.r = max(0, lin.r - jug.d_r)
            lin.rbi = max(0, lin.rbi - jug.d_rbi); lin.bb = max(0, lin.bb - jug.d_bb)
            lin.hbp = max(0, lin.hbp - jug.d_hbp); lin.sf = max(0, lin.sf - jug.d_sf)
            if hasattr(lin, 'k'): lin.k = max(0, lin.k - (1 if jug.resultado == 'k' else 0))
            lin.save()
            j = jug.bateador; j.hr = max(0, j.hr - jug.d_hr); j.rbi = max(0, j.rbi - jug.d_rbi); j.avg = lin.avg
            j.save(update_fields=['hr', 'rbi', 'avg'])
    # revierte pitcher
    if jug.pitcher and jug.d_kpit:
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        if pl: pl.k = max(0, pl.k - jug.d_kpit); pl.ip_outs = max(0, pl.ip_outs - (1 if jug.resultado in RESULTADOS_OUT else 0)); pl.save()
    elif jug.pitcher and jug.resultado in RESULTADOS_OUT:
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        if pl: pl.ip_outs = max(0, pl.ip_outs - 1); pl.save()
    if jug.pitcher and jug.resultado in ('bb', 'hbp'):
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        if pl: pl.bb = max(0, pl.bb - 1); pl.save()
    if jug.pitcher and jug.d_h:
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        if pl:
            pl.h = max(0, pl.h - 1); pl.r = max(0, pl.r - jug.carreras); pl.er = max(0, pl.er - jug.carreras); pl.save()
    # revierte entrada del inning donde se registró
    ent = juego.entradas.filter(numero=jug.inning_num).first()
    if ent:
        es_loc = (jug.equipo_batea_id == juego.local_id)
        if es_loc:
            ent.carreras_local = max(0, ent.carreras_local - jug.carreras)
            if jug.d_h: ent.hits_local = max(0, ent.hits_local - 1)
        else:
            ent.carreras_visita = max(0, ent.carreras_visita - jug.carreras)
            if jug.d_h: ent.hits_visita = max(0, ent.hits_visita - 1)
        ent.save()
    # restaura juego
    juego.outs = jug.s_outs; juego.bolas = jug.s_bolas; juego.strikes = jug.s_strikes
    juego.inning_num = max(1, jug.s_inning); juego.mitad = jug.s_mitad
    juego.carreras_local = jug.s_cl; juego.carreras_visita = jug.s_cv
    if jug.equipo_batea_id == juego.local_id: juego.idx_local = jug.s_idx
    else: juego.idx_visita = jug.s_idx
    juego.sync_inning_txt(); juego.save()
    txt = jug.descripcion
    jug.delete()
    return JsonResponse({'ok': True, 'state': _estado(juego), 'deshecho': txt})


@login_required
def api_pitcher(request, pk):
    import json
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    juego = get_object_or_404(Juego, pk=pk)
    eq_id = data.get('equipo_id'); jug_id = data.get('jugador_id')
    jug = get_object_or_404(Jugador, pk=jug_id, equipo_id=eq_id)
    if int(eq_id) == juego.local_id: juego.pitcher_local = jug
    else: juego.pitcher_visita = jug
    juego.save()
    return JsonResponse({'ok': True, 'state': _estado(juego)})
