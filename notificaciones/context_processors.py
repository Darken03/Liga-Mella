def notificaciones(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'notif_count': 0, 'notif_items': []}
    try:
        qs = request.user.notificaciones.all()
        return {
            'notif_count': qs.filter(leida=False).count(),
            'notif_items': list(qs[:8]),
        }
    except Exception:
        return {'notif_count': 0, 'notif_items': []}
