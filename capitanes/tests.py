from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from equipos.models import Equipo

User = get_user_model()


TEST_STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


def _mk_admin():
    u = User.objects.create_user(username='adm1', password='x')
    u.rol = 'admin'
    u.is_staff = True
    u.save()
    return u


def _mk_capitan():
    u = User.objects.create_user(username='cap1', password='x', rol='capitan')
    eq = Equipo.objects.create(nombre='Tigres', sigla='TIG')
    eq.capitan = u
    eq.save()
    return u, eq


class AdminEquipoContextoTest(TestCase):
    storages_override = override_settings(STORAGES=TEST_STORAGES)

    @classmethod
    def setUpClass(cls):
        cls.storages_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.storages_override.disable()
    def test_admin_fija_equipo_y_mi_equipo_lo_respeta(self):
        admin = _mk_admin()
        e1 = Equipo.objects.create(nombre='A', sigla='A')
        e2 = Equipo.objects.create(nombre='B', sigla='B')
        c = Client()
        c.force_login(admin)
        r = c.post('/capitan/seleccionar/', {'equipo_id': e2.id})
        self.assertIn(r.status_code, (200, 302), r.content[:300] if r.status_code == 200 else '')
        # el dashboard del capitan muestra el equipo seleccionado
        r2 = c.get('/capitan/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'B')

    def test_no_admin_no_puede_fijar_contexto(self):
        u, eq = _mk_capitan()
        otro = Equipo.objects.create(nombre='Otro', sigla='OTR')
        c = Client()
        c.force_login(u)
        c.post('/capitan/seleccionar/', {'equipo_id': otro.id})
        r2 = c.get('/capitan/')
        self.assertEqual(r2.status_code, 200)
        # sigue viendo su equipo real, no el intentado
        self.assertContains(r2, eq.nombre)

    def test_admin_puede_anotar_y_ver_accesos(self):
        admin = _mk_admin()
        c = Client()
        c.force_login(admin)
        r = c.get('/anotador/')
        self.assertEqual(r.status_code, 200)
        r2 = c.get('/admin-liga/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, '/anotador/')
        self.assertContains(r2, 'seleccionar')
