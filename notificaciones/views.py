from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Notificacion


@login_required
def lista(request):
    notifs = request.user.notificaciones.all()[:80]
    return render(request, 'notificaciones/lista.html', {'notifs': notifs})


@login_required
def leer_y_ir(request, pk):
    n = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
    if not n.leida:
        n.leida = True
        n.save(update_fields=['leida'])
    return redirect(n.url or 'notif_lista')


@login_required
def marcar_todas(request):
    if request.method == 'POST':
        request.user.notificaciones.filter(leida=False).update(leida=True)
    # vuelve a donde estaba
    nxt = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/cuenta/notificaciones/'
    return redirect(nxt)


@login_required
def api_no_leidas(request):
    qs = request.user.notificaciones.filter(leida=False).order_by('-creada')[:8]
    return JsonResponse({
        'count': request.user.notificaciones.filter(leida=False).count(),
        'items': [{'id': n.id, 'tipo': n.tipo, 'icono': n.icono, 'titulo': n.titulo, 'mensaje': n.mensaje, 'url': f'/cuenta/notificaciones/{n.id}/ir/', 'creada': n.creada.strftime('%d %b %H:%M')} for n in qs],
    })
