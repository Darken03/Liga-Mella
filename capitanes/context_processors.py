from .views import es_admin_user, equipo_admin_activo
from equipos.models import Equipo


def equipo_admin(request):
    """Expone el contexto de administración a base_capitan.html."""
    u = getattr(request, 'user', None)
    if not u or not u.is_authenticated or not es_admin_user(u):
        return {}
    actual = equipo_admin_activo(request)
    return {
        'es_admin': True,
        'equipo_admin': actual,
        'todos_equipos': list(Equipo.objects.order_by('nombre').only('id', 'nombre')),
    }
