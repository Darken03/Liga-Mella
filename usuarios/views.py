from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from equipos.models import SolicitudTraslado, aceptar_solicitud
from .models import User
from notificaciones.models import crear as crear_notif

class MellaLogin(LoginView):
    template_name = 'usuarios/login.html'

def registro(request):
    if request.method == 'POST':
        d = request.POST
        if User.objects.filter(username=d.get('username')).exists():
            return render(request, 'usuarios/registro.html', {'error': 'Ese username ya existe.'})
        if not d.get('username') or not d.get('password'):
            return render(request, 'usuarios/registro.html', {'error': 'Usuario y contraseña obligatorios.'})
        u = User(username=d['username'], first_name=d.get('first_name', ''), last_name=d.get('last_name', ''),
                 ci=d.get('ci', ''), estatura=d.get('estatura', ''), rol='fan')
        u.edad = int(d['edad']) if d.get('edad') else None
        u.set_password(d['password']); u.save()
        login(request, u)
        messages.success(request, 'Cuenta creada. ¡Bienvenido!')
        return redirect('/cuenta/redirigir/')
    return render(request, 'usuarios/registro.html')

@login_required
def redirigir(request):
    u = request.user
    if u.es_admin(): return redirect('/admin-liga/')
    if u.es_capitan() or u.es_director(): return redirect('/capitan/')
    if u.es_anotador(): return redirect('/anotador/')
    return redirect('/cuenta/perfil/')

@login_required
def configurar(request):
    """Configurar cuenta: datos personales y cambio de contraseña.

    Vale para jugadores, capitanes y directores (cada uno edita lo suyo).
    Para cambiar la clave hay que confirmar la actual.
    """
    from django.contrib.auth import update_session_auth_hash
    u = request.user
    if request.method == 'POST':
        acc = request.POST.get('accion', 'datos')
        if acc == 'datos':
            u.first_name = (request.POST.get('first_name') or '').strip()[:150]
            u.last_name = (request.POST.get('last_name') or '').strip()[:150]
            u.ci = (request.POST.get('ci') or '').strip()[:30]
            u.estatura = (request.POST.get('estatura') or '').strip()[:10]
            u.telefono = (request.POST.get('telefono') or '').strip()[:30]
            edad_txt = (request.POST.get('edad') or '').strip()
            try:
                u.edad = int(edad_txt) if edad_txt else None
            except (TypeError, ValueError):
                messages.error(request, 'La edad debe ser un número.')
                return redirect('configurar')
            u.save()
            messages.success(request, 'Tus datos fueron actualizados.')
        elif acc == 'clave':
            actual = request.POST.get('actual') or ''
            n1 = request.POST.get('nueva1') or ''
            n2 = request.POST.get('nueva2') or ''
            if not u.check_password(actual):
                messages.error(request, 'Tu contraseña actual no es correcta.')
                return redirect('configurar')
            if n1 != n2:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
                return redirect('configurar')
            if len(n1) < 6:
                messages.error(request, 'La nueva contraseña debe tener al menos 6 caracteres.')
                return redirect('configurar')
            u.set_password(n1)
            u.save()
            update_session_auth_hash(request, u)
            messages.success(request, 'Contraseña cambiada. Sigues en sesión.')
        return redirect('configurar')
    return render(request, 'usuarios/configurar.html')


@login_required
def mi_perfil(request):
    """Mi Perfil del jugador: sus estadísticas + editar foto y portada."""
    from core.views import _totales_jugador
    u = request.user
    j = getattr(u, 'ficha_jugador', None)
    if j is not None and request.method == 'POST' and request.POST.get('accion') == 'fotos':
        for campo in ('foto', 'portada'):
            quitar = request.POST.get(f'quitar_{campo}')
            nuevo = request.FILES.get(campo)
            actual = getattr(j, campo)
            if nuevo:
                if nuevo.size > 5 * 1024 * 1024:
                    messages.error(request, f'La imagen de {"perfil" if campo == "foto" else "portada"} supera los 5 MB.')
                    return redirect('mi_perfil')
                if actual:
                    try:
                        actual.delete(save=False)
                    except Exception:
                        pass
                setattr(j, campo, nuevo)
            elif quitar and not nuevo:
                if actual:
                    try:
                        actual.delete(save=False)
                    except Exception:
                        pass
                setattr(j, campo, None)
        try:
            j.full_clean(exclude=['equipo', 'nombre', 'usuario'])
            j.save()
            messages.success(request, 'Tus fotos fueron actualizadas.')
        except Exception as e:
            messages.error(request, f'No se pudo guardar: {e}.')
        return redirect('mi_perfil')
    lineas = tot = None
    if j is not None:
        lineas = j.lineas.select_related('torneo').order_by('-torneo__id')
        tot = _totales_jugador(j.id)
    return render(request, 'usuarios/perfil.html', {'j': j, 'lineas': lineas, 'tot': tot})

@login_required
def mis_solicitudes(request):
    return render(request, 'usuarios/solicitudes.html', {'solicitudes': request.user.solicitudes_recibidas.all()})

@login_required
def solicitud_detalle(request, pk):
    s = get_object_or_404(SolicitudTraslado, pk=pk, usuario=request.user)
    return render(request, 'usuarios/solicitud_detalle.html', {'s': s})

@login_required
def solicitud_aceptar(request, pk):
    s = get_object_or_404(SolicitudTraslado, pk=pk, usuario=request.user, estado='pendiente')
    if request.method == 'POST':
        if not request.user.check_password(request.POST.get('password') or ''):
            messages.error(request, 'Contraseña incorrecta. No se aceptó la solicitud.')
            return redirect('sol_detalle', pk=pk)
        if not aceptar_solicitud(s):
            messages.error(request, f'{s.equipo.nombre} está cerrado: no acepta nuevos jugadores en este momento.')
            return redirect('mis_solicitudes')
        messages.success(request, f'¡Bienvenido a {s.equipo.nombre}!')
        if s.creado_por and s.creado_por_id != request.user.id:
            crear_notif(s.creado_por, 'fichaje_aceptado', f"@{request.user.username} aceptó unirse a {s.equipo.nombre}",
                        f"{request.user.username} aceptó tu invitación a {s.equipo.nombre}.", url='/capitan/fichajes/')
    return redirect('mis_solicitudes')

@login_required
def solicitud_rechazar(request, pk):
    s = get_object_or_404(SolicitudTraslado, pk=pk, usuario=request.user, estado='pendiente')
    if request.method == 'POST':
        s.estado = 'rechazada'; s.save()
        messages.info(request, f'Rechazaste unirte a {s.equipo.nombre}.')
        if s.creado_por and s.creado_por_id != request.user.id:
            crear_notif(s.creado_por, 'fichaje_rechazado', f"@{request.user.username} rechazó {s.equipo.nombre}",
                        f"{request.user.username} rechazó tu invitación a {s.equipo.nombre}.", url='/capitan/fichajes/')
    return redirect('mis_solicitudes')
