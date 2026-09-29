from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from usuarios.models import User
from equipos.models import Equipo, Jugador
from torneos.models import Torneo, Juego
from core.models import Noticia

class Command(BaseCommand):
    def handle(self, *args, **o):
        admin,_ = User.objects.get_or_create(username='admin', defaults={'rol':'admin','is_staff':True,'is_superuser':True})
        admin.set_password('mella123'); admin.rol='admin'; admin.is_staff=True; admin.is_superuser=True; admin.save()
        cap,_ = User.objects.get_or_create(username='capitan', defaults={'rol':'capitan'})
        cap.set_password('mella123'); cap.rol='capitan'; cap.save()
        ano,_ = User.objects.get_or_create(username='anotador', defaults={'rol':'anotador'})
        ano.set_password('mella123'); ano.rol='anotador'; ano.save()
        t,_ = Torneo.objects.get_or_create(nombre='Copa Mella', temporada='Apertura 2026')
        datos = [('Leones','LEO',8,2),('Toros','TOR',6,4),('Águilas','AGU',5,5),('Gigantes','GIG',3,7)]
        equipos=[]
        for nom,sig,w,l in datos:
            e,_ = Equipo.objects.get_or_create(nombre=nom, defaults={'sigla':sig,'victorias':w,'derrotas':l})
            e.sigla=sig; e.victorias=w; e.derrotas=l; e.save(); equipos.append(e)
        equipos[0].capitan=cap; equipos[0].save()
        roster=[('R. Díaz',27,'P',False,.280,2,10),('J. Cruz',5,'C',False,.310,1,8),('M. Soto',11,'1B',False,.330,6,18),('A. Peña',2,'2B',False,.350,2,12),('L. Gómez',7,'SS',True,.365,3,15),('K. Núñez',9,'3B',False,.300,2,11),('F. Ruiz',14,'LF',False,.290,3,9),('D. Mora',21,'LCF',False,.295,1,7),('E. Díaz',33,'RCF',False,.320,4,14),('P. Luna',8,'RF',False,.340,2,10)]
        for e in equipos:
            for nom,dor,pos,esc,avg,hr,rbi in roster:
                Jugador.objects.get_or_create(equipo=e, dorsal=dor, defaults={'nombre':nom,'posicion':pos,'es_capitan':esc,'avg':avg,'hr':hr,'rbi':rbi})
        if not Juego.objects.exists():
            ahora=timezone.now()
            Juego.objects.create(torneo=t, local=equipos[0], visita=equipos[1], fecha=ahora-timedelta(hours=1), estadio='Estadio Mella 1', estado='envivo', carreras_local=5, carreras_visita=4, anotador=ano)
            Juego.objects.create(torneo=t, local=equipos[2], visita=equipos[3], fecha=ahora+timedelta(days=2), estadio='Estadio Mella 2', estado='programado', anotador=ano)
        if not Noticia.objects.exists():
            Noticia.objects.create(titulo='Leones remontan en el 7mo', resumen='Doble de oro de Martínez para ganar 8-7.', torneo_tag='COPA MELLA')
            Noticia.objects.create(titulo='Nuevo torneo juvenil', resumen='Inscripciones abiertas en el play.', torneo_tag='JUVENIL')
        self.stdout.write(self.style.SUCCESS('Seed OK'))
