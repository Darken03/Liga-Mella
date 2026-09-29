# =====================================================================
# Archivo WSGI para PythonAnywhere — dominio: ligamella.pythonanywhere.com
# ---------------------------------------------------------------------
# CÓMO USARLO (una sola vez):
#  1. En la pestaña "Web" de PythonAnywhere abre el archivo WSGI de tu app
#     (ruta tipo /var/www/ligamella_pythonanywhere_com_wsgi.py).
#  2. Borra TODO su contenido y pega este archivo completo.
#  3. Ajusta PROJECT_DIR si tu carpeta del proyecto tiene otro nombre.
#  4. Genera una clave secreta y pégala en DJANGO_SECRET_KEY:
#         python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
#  5. Guarda y pulsa el botón verde "Reload".
# =====================================================================

import os
import sys

# Carpeta raíz del proyecto en PythonAnywhere.
# Recomendado: clonar/subir el proyecto como /home/ligamella/liga-mella
# (sin espacios ni tildes para evitar problemas de rutas).
PROJECT_DIR = '/home/ligamella/liga-mella'
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# --- Variables de producción (NO subir claves reales al repo) ---
os.environ['DJANGO_SECRET_KEY'] = 'PEGA-AQUI-UNA-CLAVE-GENERADA'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
