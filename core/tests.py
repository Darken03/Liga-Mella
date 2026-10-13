from django.test import TestCase, override_settings
from equipos.models import Equipo, Jugador
from torneos.models import Torneo
from estadisticas.models import ActuacionBateo, ActuacionPitcheo


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class EstadisticasEquipoTest(TestCase):
    def setUp(self):
        self.torneo = Torneo.objects.create(nombre='Apertura', temporada='2026', activo=True)
        self.eq1 = Equipo.objects.create(nombre='Tigres', sigla='TIG', color='#C81E2E')
        self.eq2 = Equipo.objects.create(nombre='Leones', sigla='LEO', color='#0A1A3A')
        self.j1 = Jugador.objects.create(equipo=self.eq1, nombre='Juan', apellido='Perez', dorsal=10, posicion='SS')
        self.j2 = Jugador.objects.create(equipo=self.eq2, nombre='Pedro', apellido='Gomez', dorsal=5, posicion='P')
        ActuacionBateo.objects.create(jugador=self.j1, torneo=self.torneo, ab=10, h=5, hr=2, rbi=6)
        ActuacionBateo.objects.create(jugador=self.j2, torneo=self.torneo, ab=8, h=2, hr=0, rbi=1)
        ActuacionPitcheo.objects.create(jugador=self.j2, torneo=self.torneo, jl=3, ip_outs=15, k=7)

    def test_filtra_por_equipo(self):
        r = self.client.get(f'/estadisticas/?torneo={self.torneo.id}&equipo={self.eq1.id}')
        self.assertEqual(r.status_code, 200)
        lineas = list(r.context['lineas'])
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].jugador.equipo_id, self.eq1.id)
        self.assertEqual(r.context['equipo_sel'].id, self.eq1.id)

    def test_muestra_botones_imprimir_y_pdf(self):
        r = self.client.get(f'/estadisticas/?torneo={self.torneo.id}&equipo={self.eq1.id}')
        self.assertContains(r, 'Imprimir')
        self.assertContains(r, 'estadisticas/pdf')

    def test_pdf_equipo_devuelve_pdf(self):
        r = self.client.get(f'/estadisticas/pdf/?torneo={self.torneo.id}&equipo={self.eq1.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/pdf', r['Content-Type'])
        self.assertTrue(r.content[:4] == b'%PDF')
