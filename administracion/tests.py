from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from equipos.models import Equipo
from torneos.models import Torneo, Juego, EquipoTorneo, finalizar_juego


def _mk_equipos():
    loc = Equipo.objects.create(nombre='La Familia', sigla='FAM')
    vis = Equipo.objects.create(nombre='Los Mets', sigla='MET')
    return loc, vis


def _mk_torneo():
    return Torneo.objects.create(nombre='T', temporada='2026')


def _mk_admin():
    User = get_user_model()
    return User.objects.create_user(username='adm', password='x', rol='admin')


class AdminRevertirTest(TestCase):
    def setUp(self):
        self.c = Client()
        self.adm = _mk_admin()
        self.c.force_login(self.adm)
        self.tor = _mk_torneo()
        self.loc, self.vis = _mk_equipos()

    def _finalizado(self, cl=5, cv=3):
        j = Juego.objects.create(torneo=self.tor, local=self.loc, visita=self.vis,
                                 fecha=timezone.now(), estado='envivo',
                                 carreras_local=cl, carreras_visita=cv)
        j.estado = 'final'
        j.save(update_fields=['estado'])
        finalizar_juego(j)
        j.refresh_from_db()
        return j

    def test_reabrir_resta_y_pasa_a_envivo(self):
        j = self._finalizado()
        r = self.c.post(f'/admin-liga/juegos/{j.id}/reabrir/')
        self.assertEqual(r.status_code, 302, r.content[:500] if r.status_code != 302 else '')
        j.refresh_from_db()
        self.assertEqual(j.estado, 'envivo')
        self.assertFalse(j.resultado_aplicado)
        lin = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        self.assertEqual(lin.ganados, 0)

    def test_reabrir_no_final_no_toca(self):
        j = Juego.objects.create(torneo=self.tor, local=self.loc, visita=self.vis,
                                 fecha=timezone.now(), estado='envivo',
                                 carreras_local=1, carreras_visita=0)
        r = self.c.post(f'/admin-liga/juegos/{j.id}/reabrir/')
        self.assertEqual(r.status_code, 302)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.victorias, 0)

    def test_eliminar_final_revierte_tabla(self):
        j = self._finalizado()
        r = self.c.post(f'/admin-liga/juegos/{j.id}/eliminar/')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Juego.objects.filter(pk=j.pk).exists())
        lin = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        self.assertEqual(lin.ganados, 0)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.victorias, 0)

    def test_recalcular_repara_inflado(self):
        j = self._finalizado()
        # infla a mano como el bug del usuario
        lin = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        lin.ganados += 1
        lin.save()
        r = self.c.post(f'/admin-liga/torneos/{self.tor.id}/recalcular/')
        self.assertEqual(r.status_code, 302)
        lin.refresh_from_db()
        self.assertEqual(lin.ganados, 1)

    def test_juego_form_no_expone_estado(self):
        from administracion.forms import JuegoForm
        self.assertNotIn('estado', JuegoForm.Meta.fields)


class AnotadorBlindajeTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.u = User.objects.create_user(username='anot', password='x')
        self.c = Client()
        self.c.force_login(self.u)
        self.tor = _mk_torneo()
        self.loc, self.vis = _mk_equipos()

    def test_doble_finalizar_api_no_duplica(self):
        import json
        j = Juego.objects.create(torneo=self.tor, local=self.loc, visita=self.vis,
                                 fecha=timezone.now(), estado='envivo',
                                 carreras_local=5, carreras_visita=3)
        r1 = self.c.post(f'/anotador/juego/{j.id}/api/control/',
                         json.dumps({'accion': 'finalizar'}), content_type='application/json')
        self.assertEqual(r1.status_code, 200)
        # segundo intento (aunque ya esté final, no debe sumar)
        j.refresh_from_db()
        from torneos.models import finalizar_juego
        finalizar_juego(j)  # llamada directa extra
        lin = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        self.assertEqual(lin.ganados, 1)
