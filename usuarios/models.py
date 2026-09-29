from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROL_CHOICES = [('admin','Administrador'),('capitan','Capitán'),('director','Director'),('anotador','Anotador'),('fan','Aficionado')]
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='fan')
    telefono = models.CharField(max_length=30, blank=True)
    ci = models.CharField(max_length=30, blank=True, verbose_name='Carnet de identidad')
    edad = models.PositiveIntegerField(null=True, blank=True)
    estatura = models.CharField(max_length=10, blank=True)
    def es_admin(self): return self.rol == 'admin' or self.is_superuser
    def es_capitan(self): return self.rol == 'capitan'
    def es_director(self): return self.rol == 'director'
    def es_mando(self): return self.rol in ('capitan', 'director')
    def es_anotador(self): return self.rol == 'anotador'
