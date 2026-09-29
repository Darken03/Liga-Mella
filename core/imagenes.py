"""Utilidad central: toda imagen subida se convierte a WebP.

Uso:
    from core.imagenes import convertir_a_webp, procesar_imagen_modelo

- convertir_a_webp(archivo, calidad=82, max_lado=1920) -> ContentFile (.webp) o None si no es convertible.
- procesar_imagen_modelo(instancia, *campos) -> convierte los ImageField indicados
  antes de guardar. Si ya es .webp, no hace nada.
"""
import os
from io import BytesIO

from django.core.files.base import ContentFile

CALIDAD_WEBP = 82
MAX_LADO = 1920

EXT_CONVERTIBLES = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}


def _nombre_webp(nombre_original):
    base = os.path.splitext(os.path.basename(nombre_original or 'imagen'))[0]
    # sanea: sin espacios ni caracteres raros
    import re
    base = re.sub(r'[^\w\-]+', '-', base, flags=re.UNICODE).strip('-') or 'imagen'
    return f'{base}.webp'


def convertir_a_webp(archivo, calidad=CALIDAD_WEBP, max_lado=MAX_LADO):
    """Convierte un archivo subido (InMemory/Temporary/File) a WebP.

    Devuelve ContentFile con nombre .webp listo para asignar al ImageField.
    Devuelve None si no es una imagen válida o no requiere conversión.
    Si ya es webp y no excede el tamaño, devuelve None (no hacer nada).
    """
    if not archivo or not getattr(archivo, 'name', None):
        return None
    nombre = archivo.name or ''
    ext = os.path.splitext(nombre)[1].lower()
    if ext not in EXT_CONVERTIBLES:
        return None  # no es imagen común (svg, avif, etc.): se deja tal cual
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        # Asegura lectura desde el inicio (UploadedFile u archivo en disco)
        try:
            archivo.seek(0)
        except Exception:
            pass
        img = Image.open(archivo)
        # GIF animado: nos quedamos con el primer frame (las noticias no necesitan animación)
        try:
            img.seek(0)
        except Exception:
            pass
        img.load()
        # Redimensiona si es muy grande (ahorra peso)
        if max_lado and max(img.size) > max_lado:
            img.thumbnail((max_lado, max_lado), Image.LANCZOS)
        # WebP soporta alfa; si no hay alfa, RGB pesa menos
        if img.mode in ('RGBA', 'LA'):
            pass  # conserva transparencia
        elif img.mode == 'P' and 'transparency' in img.info:
            img = img.convert('RGBA')
        else:
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
        buf = BytesIO()
        save_kwargs = {'format': 'WEBP', 'quality': calidad, 'method': 6}
        img.save(buf, **save_kwargs)
        buf.seek(0)
        # Si ya era webp y el resultado no mejora, igual lo devolvemos normalizado
        return ContentFile(buf.read(), name=_nombre_webp(nombre))
    except Exception:
        return None
    finally:
        try:
            archivo.seek(0)
        except Exception:
            pass


def fotos_previas(instancia, *campos):
    """Nombres guardados en BD antes de guardar (para detectar reemplazos)."""
    if not getattr(instancia, 'pk', None):
        return {}
    try:
        fila = type(instancia).objects.filter(pk=instancia.pk).values(*campos).first()
    except Exception:
        return {}
    return dict(fila or {})


def borrar_si_reemplazada(instancia, previas):
    """Borra del storage los archivos viejos que fueron reemplazados.

    Llamar DESPUÉS de super().save(): así el nombre final (con el sufijo
    que Django agrega si el nombre se repetía) ya está definido y no queda
    ningún huérfano. Ahorra espacio en disco.
    """
    for campo, viejo in (previas or {}).items():
        try:
            f = getattr(instancia, campo, None)
            nuevo = getattr(f, 'name', None) if f else None
            if viejo and nuevo and viejo != nuevo and f.storage.exists(viejo):
                f.storage.delete(viejo)
        except Exception:
            pass


def borrar_archivos(instancia, *campos):
    """Borra del storage los archivos indicados (al eliminar el objeto)."""
    for campo in campos:
        try:
            f = getattr(instancia, campo, None)
            nombre = getattr(f, 'name', None) if f else None
            if nombre and f.storage.exists(nombre):
                f.storage.delete(nombre)
        except Exception:
            pass
def procesar_imagen_modelo(instancia, *campos, calidad=CALIDAD_WEBP, max_lado=MAX_LADO):
    """Convierte los campos imagen indicados de un modelo a WebP in-place.

    Llamar al inicio de save(). Borra el archivo anterior si cambia la extensión
    para no dejar huérfanos .jpg/.png en media/.
    """
    for campo in campos:
        field_file = getattr(instancia, campo, None)
        if not field_file or not getattr(field_file, 'name', None):
            continue
        nombre_actual = field_file.name
        # Ya es webp: nada que hacer
        if nombre_actual.lower().endswith('.webp'):
            continue
        # ¿Es una subida nueva o un archivo heredado jpg? En ambos casos convertimos
        # una sola vez; tras convertir el nombre pasa a .webp y no se repite.
        archivo = None
        # Caso 1: subida nueva (tiene file en memoria)
        try:
            f = field_file.file
            # FieldFile sin archivo real lanza ValueError; lo ignoramos
            if f is not None:
                archivo = f
                # Si es un archivo ya guardado en disco y no cambió, igual lo
                # convertimos una vez para migrar los jpg antiguos.
                # Distinguimos "sin cambios" comparando con la BD.
                if instancia.pk:
                    try:
                        anterior = type(instancia).objects.filter(pk=instancia.pk).values_list(campo, flat=True).first()
                        if anterior == nombre_actual and getattr(f, 'size', None) is None:
                            pass  # sigue: es migración de jpg viejo
                    except Exception:
                        pass
        except Exception:
            continue
        if archivo is None:
            continue
        nuevo = convertir_a_webp(archivo, calidad=calidad, max_lado=max_lado)
        if nuevo is None:
            continue
        viejo = nombre_actual
        # Pasa solo el basename: FieldFile.save() aplica upload_to vía
        # generate_filename y evita duplicar carpetas (noticias/noticias/).
        field_file.save(nuevo.name, nuevo, save=False)
        # Si el nombre cambió (jpg->webp), borra el huérfano viejo del storage.
        # Solo si el viejo existe físicamente (evita borrar en flujo de alta
        # donde viejo aún no está en disco).
        if viejo and viejo != field_file.name:
            try:
                storage = field_file.storage
                if storage.exists(viejo):
                    storage.delete(viejo)
            except Exception:
                pass
