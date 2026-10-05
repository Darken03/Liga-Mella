import json
from django.test import TestCase, Client
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
