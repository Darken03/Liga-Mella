import json
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from equipos.models import Equipo, Jugador
from torneos.models import Juego, Torneo
from capitanes.models import Alineacion, AlineacionDetalle


def _mk_equipo(nombre, sigla, n=11):
    eq = Equipo.objects.create(nombre=nombre, sigla=sigla)
    jugadores = []
    for i in range(1, n + 1):
        jugadores.append(Jugador.objects.create(
            equipo=eq, nombre=f"Jug{i}", apellido=nombre,
            dorsal=i, posicion='P' if i == 1 else ('C' if i == 2 else '1B')))
    return eq, jugadores


def _mk_juego():
    tor = Torneo.objects.create(nombre="T", temporada="2026")
    loc, jloc = _mk_equipo("Local", "LOC")
    vis, jvis = _mk_equipo("Visita", "VIS")
    juego = Juego.objects.create(torneo=tor, local=loc, visita=vis,
                                 fecha=timezone.now(), estado='envivo')
    # alineacion visita con 9 titulares (primeros 9), banca = 10,11
    alin = Alineacion.objects.create(equipo=vis, juego=juego)
    for idx, j in enumerate(jvis[:9]):
        AlineacionDetalle.objects.create(alineacion=alin, jugador=j,
                                         posicion=j.posicion, orden_bateo=idx + 1)
    alin2 = Alineacion.objects.create(equipo=loc, juego=juego)
    for idx, j in enumerate(jloc[:9]):
        AlineacionDetalle.objects.create(alineacion=alin2, jugador=j,
                                         posicion=j.posicion, orden_bateo=idx + 1)
    return juego, loc, vis, jloc, jvis


class CambiosAnotadorTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anot', password='x')
        self.c = Client()
        self.c.force_login(self.user)

    def test_sustituir_banca_hereda_orden(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        sale = jvis[2]  # 3er bate, orden 3
        entra = jvis[9]  # banca #10
        r = self.c.post(f"/anotador/juego/{juego.id}/api/cambio/",
                        json.dumps({"accion": "sustituir", "equipo_id": vis.id,
                                    "sale_id": sale.id, "entra_id": entra.id}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        d = r.json()
        self.assertTrue(d.get("ok"), d)
        # el orden 3 ahora lo ocupa el sustituto
        det = AlineacionDetalle.objects.get(alineacion__juego=juego,
                                            alineacion__equipo=vis, orden_bateo=3)
        self.assertEqual(det.jugador_id, entra.id)
        # el saliente ya no esta en lineup
        self.assertFalse(AlineacionDetalle.objects.filter(
            alineacion__juego=juego, alineacion__equipo=vis,
            jugador_id=sale.id).exists())
        # turno siguiente sigue siendo el mismo orden -> el sustituto batea
        juego.refresh_from_db()
        # queda registrado en ultimas + sustitucion
        self.assertTrue(juego.jugadas.filter(tipo="cambio").exists())
        from anotador.models import Sustitucion
        self.assertTrue(Sustitucion.objects.filter(juego=juego).exists())

    def test_sustituir_con_posicion_nueva(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        sale = jvis[0]
        entra = jvis[10]
        r = self.c.post(f"/anotador/juego/{juego.id}/api/cambio/",
                        json.dumps({"accion": "sustituir", "equipo_id": vis.id,
                                    "sale_id": sale.id, "entra_id": entra.id,
                                    "posicion": "SS"}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        det = AlineacionDetalle.objects.get(alineacion__juego=juego,
                                            alineacion__equipo=vis, orden_bateo=1)
        self.assertEqual(det.jugador_id, entra.id)
        self.assertEqual(det.posicion, "SS")

    def test_swap_defensivo_no_toca_orden(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        a = jvis[0]  # orden1 pos P
        b = jvis[1]  # orden2 pos C
        # les pongo posiciones distintas para notar el swap
        from capitanes.models import AlineacionDetalle as AD
        AD.objects.filter(alineacion__juego=juego, alineacion__equipo=vis,
                          jugador=a).update(posicion="P")
        AD.objects.filter(alineacion__juego=juego, alineacion__equipo=vis,
                          jugador=b).update(posicion="C")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/cambio/",
                        json.dumps({"accion": "swap_pos", "equipo_id": vis.id,
                                    "jugador_a_id": a.id, "jugador_b_id": b.id}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        da = AD.objects.get(alineacion__juego=juego, alineacion__equipo=vis, jugador=a)
        db = AD.objects.get(alineacion__juego=juego, alineacion__equipo=vis, jugador=b)
        self.assertEqual(da.orden_bateo, 1)
        self.assertEqual(db.orden_bateo, 2)
        self.assertEqual(da.posicion, "C")
        self.assertEqual(db.posicion, "P")

    def test_sustituir_entre_titulares_intercambia(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        a = jvis[0]  # orden 1
        b = jvis[4]  # orden 5
        r = self.c.post(f"/anotador/juego/{juego.id}/api/cambio/",
                        json.dumps({"accion": "sustituir", "equipo_id": vis.id,
                                    "sale_id": a.id, "entra_id": b.id}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        from capitanes.models import AlineacionDetalle as AD
        da = AD.objects.get(alineacion__juego=juego, alineacion__equipo=vis, orden_bateo=1)
        db = AD.objects.get(alineacion__juego=juego, alineacion__equipo=vis, orden_bateo=5)
        self.assertEqual(da.jugador_id, b.id)
        self.assertEqual(db.jugador_id, a.id)

    def test_deshacer_cambio_revierte(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        sale = jvis[2]
        entra = jvis[9]
        self.c.post(f"/anotador/juego/{juego.id}/api/cambio/",
                    json.dumps({"accion": "sustituir", "equipo_id": vis.id,
                                "sale_id": sale.id, "entra_id": entra.id}),
                    content_type="application/json")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/deshacer/",
                        json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertTrue(r.json().get("ok"))
        from capitanes.models import AlineacionDetalle as AD
        det = AD.objects.get(alineacion__juego=juego, alineacion__equipo=vis, orden_bateo=3)
        self.assertEqual(det.jugador_id, sale.id)


class TurnoFCTest(TestCase):
    """Fielder's Choice: el bateador llega pero hay out al corredor.

    AB+1 sin hit, outs+1, pitcher suma 1 out a su IP, y el deshacer lo revierte.
    """
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anot_fc', password='x')
        self.c = Client()
        self.c.force_login(self.user)

    def test_fc_registra_ab_sin_hit_y_un_out(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        r = self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                        json.dumps({"resultado": "fc", "rbi": 0, "carreras": 0}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        d = r.json()
        self.assertTrue(d.get("ok"), d)
        juego.refresh_from_db()
        self.assertEqual(juego.outs, 1)
        jug = juego.jugadas.order_by('-id').first()
        self.assertEqual(jug.resultado, 'fc')
        self.assertEqual(jug.d_ab, 1)
        self.assertEqual(jug.d_h, 0)
        # el pitcher que defendía (local) sumó el out a su IP
        from estadisticas.models import ActuacionPitcheo
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        self.assertIsNotNone(pl)
        self.assertEqual(pl.ip_outs, 1)

    def test_fc_deshacer_revierte_out(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                    json.dumps({"resultado": "fc", "rbi": 0, "carreras": 0}),
                    content_type="application/json")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/deshacer/",
                        json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertTrue(r.json().get("ok"), r.json())
        juego.refresh_from_db()
        self.assertEqual(juego.outs, 0)
        self.assertFalse(juego.jugadas.exists())


class TurnoDPTest(TestCase):
    """Doble play: el bateador causa dos outs.

    AB+1 sin hit, outs+2, pitcher suma 2 outs a su IP, y el deshacer lo revierte.
    """
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anot_dp', password='x')
        self.c = Client()
        self.c.force_login(self.user)

    def test_dp_registra_ab_sin_hit_y_dos_outs(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        r = self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                        json.dumps({"resultado": "dp", "rbi": 0, "carreras": 0}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        d = r.json()
        self.assertTrue(d.get("ok"), d)
        juego.refresh_from_db()
        self.assertEqual(juego.outs, 2)
        jug = juego.jugadas.order_by('-id').first()
        self.assertEqual(jug.resultado, 'dp')
        self.assertEqual(jug.d_ab, 1)
        self.assertEqual(jug.d_h, 0)
        from estadisticas.models import ActuacionPitcheo
        pl = ActuacionPitcheo.objects.filter(jugador=jug.pitcher, torneo=juego.torneo).first()
        self.assertIsNotNone(pl)
        self.assertEqual(pl.ip_outs, 2)

    def test_dp_deshacer_revierte_dos_outs(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                    json.dumps({"resultado": "dp", "rbi": 0, "carreras": 0}),
                    content_type="application/json")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/deshacer/",
                        json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertTrue(r.json().get("ok"), r.json())
        juego.refresh_from_db()
        self.assertEqual(juego.outs, 0)
        self.assertFalse(juego.jugadas.exists())
        from estadisticas.models import ActuacionPitcheo
        self.assertFalse(ActuacionPitcheo.objects.filter(torneo=juego.torneo, ip_outs__gt=0).exists())

    def test_dp_con_un_out_cambia_de_inning(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                    json.dumps({"resultado": "out", "rbi": 0, "carreras": 0}),
                    content_type="application/json")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                        json.dumps({"resultado": "dp", "rbi": 0, "carreras": 0}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        d = r.json()
        self.assertTrue(d.get("ok"), d)
        self.assertTrue(d.get("cambio_inning"), d)
        juego.refresh_from_db()
        self.assertEqual(juego.outs, 0)


class PitcherBateaTest(TestCase):
    """El equipo elige por juego si su pitcher batea o solo lanza."""
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anot_pb', password='x')
        self.c = Client()
        self.c.force_login(self.user)

    def _sin_bateo(self, juego, vis):
        from capitanes.models import Alineacion
        alin = Alineacion.objects.get(juego=juego, equipo=vis)
        alin.pitcher_batea = False
        alin.save()
        return alin

    def test_lineup_excluye_P_si_no_batea(self):
        from anotador.views import _lineup, _ensure_pitcher
        juego, loc, vis, jloc, jvis = _mk_juego()
        pitcher = jvis[0]  # P, orden 1
        self._sin_bateo(juego, vis)
        lin = _lineup(juego, vis)
        self.assertEqual(len(lin), 8)
        self.assertNotIn(pitcher.id, [d.jugador_id for d in lin])
        # pero sigue siendo el pitcher que defiende
        self.assertEqual(_ensure_pitcher(juego, vis).id, pitcher.id)

    def test_lineup_incluye_P_por_defecto(self):
        from anotador.views import _lineup
        juego, loc, vis, jloc, jvis = _mk_juego()
        lin = _lineup(juego, vis)
        self.assertEqual(len(lin), 9)
        self.assertIn(jvis[0].id, [d.jugador_id for d in lin])

    def test_turno_salta_al_pitcher_que_no_batea(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        self._sin_bateo(juego, vis)
        # alta: batea visita; idx 0 cae en el ex-orden 2 (jvis[1])
        r = self.c.post(f"/anotador/juego/{juego.id}/api/turno/",
                        json.dumps({"resultado": "out", "rbi": 0, "carreras": 0}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertTrue(r.json().get("ok"), r.json())
        juego.refresh_from_db()
        self.assertEqual(juego.idx_visita, 1)
        jug = juego.jugadas.order_by('-id').first()
        self.assertEqual(jug.bateador_id, jvis[1].id)

    def test_editor_exige_P_si_pitcher_batea(self):
        juego, loc, vis, jloc, jvis = _mk_juego()
        cap = get_user_model().objects.create_user(username='cap_pb', password='x', rol='capitan')
        loc.capitan = cap
        loc.save()
        cc = Client()
        cc.force_login(cap)
        url = f"/capitan/alineaciones/juego/{juego.id}/"
        base = {'jugador': [str(jloc[1].id), str(jloc[2].id)],
                'posicion': ['C', '1B'], 'orden': ['1', '2'], 'notas': ''}
        # flag activo sin P -> error y no toca nada (siguen los 9 iniciales)
        r = cc.post(url, dict(base, pitcher_batea='on'))
        self.assertEqual(r.status_code, 302)
        from capitanes.models import Alineacion
        alin = Alineacion.objects.get(juego=juego, equipo=loc)
        self.assertEqual(alin.detalles.count(), 9)
        self.assertTrue(alin.pitcher_batea)
        # mismo lineup con flag apagado -> guarda y persiste
        r = cc.post(url, dict(base))
        self.assertEqual(r.status_code, 302)
        alin.refresh_from_db()
        self.assertFalse(alin.pitcher_batea)
        self.assertEqual(alin.detalles.count(), 2)


class ModoRapidoTest(TestCase):
    """Modo rápido: estadísticas sin alineación.

    Lista todo el roster de ambos equipos; se registra cualquier turno
    al bate en cualquier orden. El marcador es manual (+/-). Sin innings,
    outs ni orden de bateo obligatorio.
    """
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='rapido', password='x')
        self.c = Client()
        self.c.force_login(self.user)

    def _juego_sin_alineacion(self):
        tor = Torneo.objects.create(nombre="TR", temporada="2026")
        loc, jloc = _mk_equipo("Anfitrion", "LOC")
        vis, jvis = _mk_equipo("Visitante", "VIS")
        juego = Juego.objects.create(torneo=tor, local=loc, visita=vis, fecha=timezone.now())
        return juego, loc, vis, jloc, jvis

    def _turno(self, juego, jug, res, rbi=0, anoto=0):
        return self.c.post(f"/anotador/juego/{juego.id}/api/rapido/turno/",
                           json.dumps({"bateador_id": jug.id, "resultado": res,
                                       "rbi": rbi, "anoto": anoto}),
                           content_type="application/json")

    # --- turno libre ---
    def test_turno_libre_sin_alineacion_en_cualquier_orden(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self._turno(juego, jvis[5], 'hit', rbi=1)
        self.assertEqual(r.status_code, 200, r.content[:500])
        d = r.json()
        self.assertTrue(d.get('ok'), d)
        jug = juego.jugadas.order_by('-id').first()
        self.assertEqual(jug.bateador_id, jvis[5].id)
        self.assertEqual(jug.d_ab, 1)
        self.assertEqual(jug.d_h, 1)
        self.assertEqual(jug.d_rbi, 1)
        self.assertEqual(jug.resultado, 'hit')
        # no toca el estado del juego: idx, outs e inning intactos
        juego.refresh_from_db()
        self.assertEqual(juego.idx_visita, 0)
        self.assertEqual(juego.idx_local, 0)
        self.assertEqual(juego.outs, 0)
        self.assertEqual(juego.inning_num, 1)

    def test_turno_rapido_no_toca_pitcheo_ni_entradas(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self._turno(juego, jloc[3], 'hit')
        from estadisticas.models import ActuacionPitcheo
        self.assertFalse(ActuacionPitcheo.objects.filter(torneo=juego.torneo).exists())
        self.assertFalse(juego.entradas.exists())

    def test_turno_rapido_acumula_estadisticas(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self._turno(juego, jloc[3], 'hit', rbi=2)
        self._turno(juego, jloc[3], 'hr', rbi=1)
        self._turno(juego, jloc[3], 'bb')
        from estadisticas.models import ActuacionBateo
        lin = ActuacionBateo.objects.get(jugador=jloc[3], torneo=juego.torneo)
        self.assertEqual((lin.ab, lin.h, lin.hr, lin.rbi, lin.bb), (2, 2, 1, 3, 1))
        # el HR suma la carrera anotada al propio bateador
        self.assertEqual(lin.r, 1)
        # campos denormalizados del jugador se actualizan
        jloc[3].refresh_from_db()
        self.assertEqual(jloc[3].hr, 1)
        self.assertEqual(jloc[3].rbi, 3)
        self.assertEqual(jloc[3].avg, 1.0)

    def test_turno_rapido_programado_pasa_a_envivo(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self.assertEqual(juego.estado, 'programado')
        self._turno(juego, jvis[0], 'out')
        juego.refresh_from_db()
        self.assertEqual(juego.estado, 'envivo')

    def test_hr_sin_ci_impulsa_una(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self._turno(juego, jvis[1], 'hr')
        self.assertEqual(r.status_code, 200, r.content[:500])
        jug = juego.jugadas.order_by('-id').first()
        self.assertGreaterEqual(jug.d_rbi, 1)

    def test_turno_rapido_rechaza_jugador_ajeno(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        _, otros = _mk_equipo("Ajeno", "AJE", n=3)
        r = self._turno(juego, otros[0], 'hit')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(juego.jugadas.exists())

    def test_turno_rapido_rechaza_resultado_invalido(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self._turno(juego, jvis[0], 'doblepe')
        self.assertEqual(r.status_code, 400)

    def test_turno_rapido_rechaza_jugador_invalido(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/turno/",
                        json.dumps({"bateador_id": "abc", "resultado": "hit"}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_finalizado_rechaza_turno(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        juego.estado = 'final'; juego.save()
        r = self._turno(juego, jvis[0], 'hit')
        self.assertEqual(r.status_code, 400)

    # --- deshacer por equipo ---
    def test_deshacer_rapido_revierte_equipo_indicado(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self._turno(juego, jvis[0], 'hit')
        self._turno(juego, jloc[0], 'hr')
        self.assertEqual(juego.jugadas.count(), 2)
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/deshacer/",
                        json.dumps({"equipo_id": jvis[0].equipo_id}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertTrue(r.json().get('ok'), r.json())
        # se borra la jugada de la visita y revierte su linea; la del local queda
        self.assertEqual(juego.jugadas.count(), 1)
        from estadisticas.models import ActuacionBateo
        lv = ActuacionBateo.objects.get(jugador=jvis[0], torneo=juego.torneo)
        self.assertEqual((lv.ab, lv.h), (0, 0))
        ll = ActuacionBateo.objects.get(jugador=jloc[0], torneo=juego.torneo)
        self.assertEqual((ll.ab, ll.h, ll.hr), (1, 1, 1))

    def test_deshacer_rapido_sin_jugadas_del_equipo(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self._turno(juego, jloc[0], 'hit')
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/deshacer/",
                        json.dumps({"equipo_id": vis.id}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 400)

    # --- marcador manual ---
    def test_puntuar_ajusta_marcador(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                        json.dumps({"equipo": "visita", "delta": 2}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                        json.dumps({"equipo": "local", "delta": 3}),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        juego.refresh_from_db()
        self.assertEqual(juego.carreras_visita, 2)
        self.assertEqual(juego.carreras_local, 3)
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                        json.dumps({"equipo": "visita", "delta": -1}),
                        content_type="application/json")
        juego.refresh_from_db()
        self.assertEqual(juego.carreras_visita, 1)
        # nunca negativo
        self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                    json.dumps({"equipo": "visita", "delta": -5}),
                    content_type="application/json")
        juego.refresh_from_db()
        self.assertEqual(juego.carreras_visita, 0)

    # --- iniciar / finalizar ---
    def test_iniciar_y_finalizar_aplican_resultado(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        self.assertEqual(juego.estado, 'programado')
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/control/",
                        json.dumps({"accion": "iniciar"}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        juego.refresh_from_db()
        self.assertEqual(juego.estado, 'envivo')
        # marcador: visita gana 3-1
        self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                    json.dumps({"equipo": "visita", "delta": 3}), content_type="application/json")
        self.c.post(f"/anotador/juego/{juego.id}/api/rapido/puntuar/",
                    json.dumps({"equipo": "local", "delta": 1}), content_type="application/json")
        r = self.c.post(f"/anotador/juego/{juego.id}/api/rapido/control/",
                        json.dumps({"accion": "finalizar"}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:500])
        juego.refresh_from_db()
        self.assertEqual(juego.estado, 'final')
        self.assertTrue(juego.resultado_aplicado)
        vis.refresh_from_db()
        self.assertEqual(vis.victorias, 1)
        loc.refresh_from_db()
        self.assertEqual(loc.derrotas, 1)
        from torneos.models import EquipoTorneo
        linv = EquipoTorneo.objects.get(equipo=vis, torneo=juego.torneo)
        self.assertEqual((linv.ganados, linv.ca, linv.cp), (1, 3, 1))
        # finalizar de nuevo no duplica (idempotente)
        self.c.post(f"/anotador/juego/{juego.id}/api/rapido/control/",
                    json.dumps({"accion": "finalizar"}), content_type="application/json")
        vis.refresh_from_db()
        self.assertEqual(vis.victorias, 1)

    # --- pagina ---
    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_pagina_rapido_renderiza_todos_los_jugadores(self):
        juego, loc, vis, jloc, jvis = self._juego_sin_alineacion()
        r = self.c.get(f"/anotador/juego/{juego.id}/rapido/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, jvis[0].nombre)
        self.assertContains(r, jloc[0].nombre)
