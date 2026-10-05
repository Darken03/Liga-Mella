from django.test import TestCase
from django.utils import timezone
from equipos.models import Equipo
from torneos.models import Torneo, Juego, EquipoTorneo, finalizar_juego


def _mk(torneo, local, visita, cl, cv, fase='regular', estado='programado'):
    return Juego.objects.create(
        torneo=torneo, local=local, visita=visita,
        fecha=timezone.now(), estadio='Mella 1',
        fase=fase, estado=estado,
        carreras_local=cl, carreras_visita=cv,
    )


class BlindajeTablaTest(TestCase):
    def setUp(self):
        self.tor = Torneo.objects.create(nombre='T', temporada='2026')
        self.loc = Equipo.objects.create(nombre='La Familia', sigla='FAM')
        self.vis = Equipo.objects.create(nombre='Los Mets', sigla='MET')

    def test_doble_finalizar_no_duplica(self):
        """Reproduce el bug: finalizar dos veces sumaba +2."""
        j = _mk(self.tor, self.loc, self.vis, 5, 3, estado='envivo')
        j.estado = 'final'
        j.save(update_fields=['estado'])
        finalizar_juego(j)
        # segundo intento (reapertura accidental + refinalizar)
        finalizar_juego(j)

        self.loc.refresh_from_db(); self.vis.refresh_from_db()
        lin_loc = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        lin_vis = EquipoTorneo.objects.get(equipo=self.vis, torneo=self.tor)
        self.assertEqual(lin_loc.ganados, 1)
        self.assertEqual(lin_vis.perdidos, 1)
        self.assertEqual(self.loc.victorias, 1)
        self.assertEqual(self.vis.derrotas, 1)
        self.assertEqual(lin_loc.ca, 5)
        self.assertEqual(lin_vis.cp, 5)

    def test_revertir_resta_tabla(self):
        j = _mk(self.tor, self.loc, self.vis, 5, 3, estado='envivo')
        j.estado = 'final'
        j.save(update_fields=['estado'])
        finalizar_juego(j)
        from torneos.models import revertir_juego
        j.refresh_from_db()
        revertir_juego(j)

        self.loc.refresh_from_db(); self.vis.refresh_from_db()
        lin_loc = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        lin_vis = EquipoTorneo.objects.get(equipo=self.vis, torneo=self.tor)
        self.assertEqual(lin_loc.ganados, 0)
        self.assertEqual(lin_vis.perdidos, 0)
        self.assertEqual(self.loc.victorias, 0)
        self.assertEqual(self.vis.derrotas, 0)
        self.assertEqual(lin_loc.ca, 0)
        self.assertEqual(lin_vis.cp, 0)
        j.refresh_from_db()
        self.assertFalse(j.resultado_aplicado)
        self.assertEqual(j.estado, 'envivo')

    def test_revertir_sin_aplicar_no_resta_en_negativo(self):
        from torneos.models import revertir_juego
        j = _mk(self.tor, self.loc, self.vis, 5, 3, estado='envivo')
        revertir_juego(j)
        self.loc.refresh_from_db(); self.vis.refresh_from_db()
        self.assertEqual(self.loc.victorias, 0)
        self.assertEqual(self.vis.derrotas, 0)

    def test_finalizar_empate_no_suma_wl_pero_si_carreras_y_revierte(self):
        j = _mk(self.tor, self.loc, self.vis, 4, 4, estado='envivo')
        j.estado = 'final'
        j.save(update_fields=['estado'])
        finalizar_juego(j)
        from torneos.models import revertir_juego
        lin_loc = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        self.assertEqual(lin_loc.ganados, 0)
        self.assertEqual(lin_loc.ca, 4)
        j.refresh_from_db()
        revertir_juego(j)
        lin_loc.refresh_from_db()
        self.assertEqual(lin_loc.ca, 0)

    def test_recalcular_repara_tabla_inflada(self):
        from torneos.models import recalcular_torneo
        j = _mk(self.tor, self.loc, self.vis, 5, 3, estado='final')
        # simula tabla inflada a mano (el bug del usuario: 3 en vez de 2)
        # aquí: 1 juego real pero tabla dice 2-0
        EquipoTorneo.objects.create(equipo=self.loc, torneo=self.tor, ganados=2, perdidos=0, ca=10, cp=6)
        EquipoTorneo.objects.create(equipo=self.vis, torneo=self.tor, ganados=0, perdidos=2, ca=6, cp=10)
        self.loc.victorias = 2; self.loc.save()
        self.vis.derrotas = 2; self.vis.save()
        recalcular_torneo(self.tor)
        lin_loc = EquipoTorneo.objects.get(equipo=self.loc, torneo=self.tor)
        lin_vis = EquipoTorneo.objects.get(equipo=self.vis, torneo=self.tor)
        self.assertEqual(lin_loc.ganados, 1)
        self.assertEqual(lin_vis.perdidos, 1)
        self.assertEqual(lin_loc.ca, 5)
