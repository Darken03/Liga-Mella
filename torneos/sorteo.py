"""Sorteo automático de calendario round-robin.

Formato de la liga:
- Cada domingo una pareja juega IDA y VUELTA el mismo día (2 juegos por equipo),
  pero NO seguidos: primero rotan todos (idas 9:00, 10:00, 11:00) y luego se
  repite la rotación (vueltas 12:00, 13:00, 14:00). Ej.: Clásicos vs Comboys
  juegan el 1ero y el 4to.
- Cada equipo enfrenta a todos los demás una vez -> 10 juegos en 5 domingos (6 equipos).
- Bloques de 1 hora. 6 partidos por domingo.
- Los horarios rotan cada domingo: si a un equipo le tocó las 9:00, el próximo
  domingo le toca otro bloque (10:00 u 11:00). Puede coincidir alguna vez, es
  normal, pero el sorteo reparte los horarios entre todos.

Si a futuro hay otro número de equipos el algoritmo se adapta:
- N par: N-1 domingos, todos juegan cada domingo.
- N impar: N domingos, cada domingo descansa un equipo.
"""
import random
from datetime import date, datetime, time, timedelta

DOMINGO = 6  # weekday(): lunes=0 ... domingo=6


def primer_domingo(desde):
    """Primer domingo en/tras la fecha dada."""
    if isinstance(desde, datetime):
        desde = desde.date()
    while desde.weekday() != DOMINGO:
        desde += timedelta(days=1)
    return desde


def proximo_domingo_hoy():
    from django.utils import timezone
    return primer_domingo(timezone.localdate())


def rondas_round_robin(ids_equipos, seed=None):
    """Devuelve lista de rondas; cada ronda es lista de parejas (a, b).

    Con N impar se añade un None (bye) y la pareja con None se salta.
    """
    ids = list(ids_equipos)
    if seed is not None:
        rnd = random.Random(seed)
        rnd.shuffle(ids)
    else:
        random.shuffle(ids)
    if len(ids) % 2 == 1:
        ids.append(None)
    n = len(ids)
    rondas = []
    fijos = list(ids)
    for _ in range(n - 1):
        ronda = []
        for i in range(n // 2):
            a, b = fijos[i], fijos[n - 1 - i]
            if a is not None and b is not None:
                # alterna localía de la ida por ronda para repartir
                ronda.append((a, b) if len(rondas) % 2 == 0 else (b, a))
        rondas.append(ronda)
        # rotación del círculo: primero fijo, el resto gira
        fijos = [fijos[0]] + [fijos[-1]] + fijos[1:-1]
    # orden aleatorio de las jornadas para que el sorteo no sea predecible
    if seed is not None:
        rnd.shuffle(rondas)
    else:
        random.shuffle(rondas)
    return rondas


def _elegir_orden(ronda, uso, ultimo):
    """Ordena las parejas de un domingo en los bloques horarios buscando que
    cada equipo rote: prefiere los bloques que menos ha usado cada equipo y
    penaliza repetir el bloque del domingo anterior. Empates al azar."""
    import itertools
    pares = list(ronda)
    k = len(pares)
    if k > 7:  # evita explosión factorial con muchísimos equipos
        orden = list(pares)
        random.shuffle(orden)
        return orden
    mejor, mejores = None, []
    for perm in itertools.permutations(range(k)):
        costo = 0
        for slot, idx in enumerate(perm):
            for eq in pares[idx]:
                costo += uso.get(eq, {}).get(slot, 0) * 10
                if ultimo.get(eq) == slot:
                    costo += 5
        if mejor is None or costo < mejor:
            mejor, mejores = costo, [perm]
        elif costo == mejor:
            mejores.append(perm)
    return [pares[i] for i in random.choice(mejores)]


def generar_sorteo(torneo, equipos, fecha_inicio=None, hora_inicio=9, seed=None,
                   fija_local=None, fija_visita=None):
    """Crea los Juegos del torneo y las líneas de posiciones.

    - torneo: instancia Torneo ya guardada.
    - equipos: iterable de Equipo (o ids). Mínimo 2.
    - fecha_inicio: date/datetime del primer domingo (si no es domingo, se
      avanza al domingo siguiente). Si es None, próximo domingo desde hoy.
    - hora_inicio: hora local del primer juego del domingo (9 = 9:00).
    - fija_local / fija_visita: ids de la pareja del juego inaugural
      (tradición: los finalistas abren el campeonato). Su ida queda como
      primer juego del primer domingo (a la hora_inicio) y el resto del
      sorteo se arma con los demás equipos rotando los otros fines de semana.
      El inaugural cuenta como juego normal: el día 1 sigue teniendo los
      mismos juegos, no se agrega ninguno extra.
    Devuelve {'domingos': [date...], 'juegos': int, 'equipos': int}.
    """
    from django.utils import timezone
    from .models import Juego, EquipoTorneo

    lista = list(equipos)
    if len(lista) < 2:
        raise ValueError('Selecciona al menos 2 equipos para el sorteo.')
    ids = [e.id if hasattr(e, 'id') else int(e) for e in lista]

    if fecha_inicio is None:
        d0 = proximo_domingo_hoy()
    else:
        d0 = fecha_inicio.date() if isinstance(fecha_inicio, datetime) else fecha_inicio
    d0 = primer_domingo(d0)
    try:
        h0 = min(23, max(0, int(hora_inicio)))
    except (TypeError, ValueError):
        h0 = 9

    rondas = rondas_round_robin(ids, seed=seed)
    # Pareja inaugural fija: su ronda pasa al primer domingo para que abran.
    fija = None
    if fija_local and fija_visita and fija_local != fija_visita:
        par = {int(fija_local), int(fija_visita)}
        for i, ronda in enumerate(rondas):
            for a, b in ronda:
                if {a, b} == par:
                    fija = (a, b)
                    rondas.insert(0, rondas.pop(i))
                    break
            if fija:
                break
    tz = timezone.get_default_timezone()
    juegos = []
    domingos = []
    uso = {}     # equipo_id -> {slot: veces que jugó la ida en ese bloque}
    ultimo = {}  # equipo_id -> slot de ida del domingo anterior
    for idx, ronda in enumerate(rondas):
        dia = d0 + timedelta(days=7 * idx)
        domingos.append(dia)
        # orden de las parejas con rotación de horarios (sorteo equilibrado)
        orden = _elegir_orden(ronda, uso, ultimo)
        if idx == 0 and fija:
            # la pareja inaugural abre el torneo: primera de las idas
            orden = [p for p in orden if set(p) == set(fija)] + [p for p in orden if set(p) != set(fija)]
        for slot, (a, b) in enumerate(orden):
            for eq in (a, b):
                conteo = uso.setdefault(eq, {})
                conteo[slot] = conteo.get(slot, 0) + 1
                ultimo[eq] = slot
        # Rotación: primero todas las IDAS y luego todas las VUELTAS en el
        # mismo orden, para que ningún equipo juegue dos seguidos
        # (el 1ero y el 4to son la misma pareja ida/vuelta, etc.).
        turnos = [(a, b) for a, b in orden] + [(b, a) for a, b in orden]
        marca_inaug = None
        if idx == 0 and fija:
            # inaugural: abre el torneo con local/visita elegidos; la vuelta
            # queda invertida para no alterar el balance
            a, b = int(fija_local), int(fija_visita)
            turnos[0] = (a, b)
            turnos[len(orden)] = (b, a)
            marca_inaug = 0
        hora = h0
        for pos, (local, visita) in enumerate(turnos):
            naive = datetime.combine(dia, time(hour=hora, minute=0))
            juegos.append(Juego(
                torneo=torneo, local_id=local, visita_id=visita,
                fecha=timezone.make_aware(naive, tz),
                estado='programado',
                serie='INAUG' if pos == marca_inaug else '',
            ))
            hora += 1
    Juego.objects.bulk_create(juegos)
    for eid in ids:
        EquipoTorneo.objects.get_or_create(equipo_id=eid, torneo=torneo)
    return {'domingos': domingos, 'juegos': len(juegos), 'equipos': len(ids)}
