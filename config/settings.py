from pathlib import Path
import os
import dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent
# En PythonAnywhere se define DJANGO_SECRET_KEY en el archivo WSGI.
# En Render se define como env var. Nunca subir la clave real al repo.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-liga-mella-dev-key-cambiar-en-prod')
# En local: True (valor por defecto). En PythonAnywhere/Render: DJANGO_DEBUG=False.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    'ligamella.pythonanywhere.com,www.ligamella.pythonanywhere.com,localhost,127.0.0.1',
).split(',')
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'DJANGO_CSRF_TRUSTED',
    'https://ligamella.pythonanywhere.com,https://www.ligamella.pythonanywhere.com',
).split(',')
# Render: añade automáticamente el hostname externo (ej. liga-mella.onrender.com)
RENDER_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOSTNAME:
    if RENDER_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_HOSTNAME)
    origin = f'https://{RENDER_HOSTNAME}'
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'crispy_forms',
    'crispy_bootstrap5',
    'usuarios',
    'equipos',
    'torneos',
    'estadisticas',
    'core',
    'administracion',
    'capitanes',
    'anotador',
    'notificaciones',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates','DIRS': [BASE_DIR / 'templates'],'APP_DIRS': True,'OPTIONS': {'context_processors': ['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','notificaciones.context_processors.notificaciones',],},},]
WSGI_APPLICATION = 'config.wsgi.application'
# Render provee DATABASE_URL (Postgres). En local/PythonAnywhere cae a SQLite.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'es-do'
TIME_ZONE = 'America/Santo_Domingo'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Render está detrás de un proxy HTTPS
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'usuarios.User'
LOGIN_URL = '/cuenta/login/'
LOGIN_REDIRECT_URL = '/cuenta/redirigir/'
LOGOUT_REDIRECT_URL = '/'
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'
