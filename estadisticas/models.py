from django.db import models
from equipos.models import Jugador
from torneos.models import Torneo

class Liderato(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE)
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE)
    avg = models.FloatField(default=0); hr = models.PositiveIntegerField(default=0); rbi = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.jugador} {self.torneo}"

class ActuacionBateo(models.Model):
    """Línea ofensiva de un jugador en un torneo. AVG = H / AB."""
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='lineas')
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='bateo')
    ab = models.PositiveIntegerField(default=0, verbose_name='Turnos (AB)')
    r = models.PositiveIntegerField(default=0, verbose_name='Anotadas (R)')
    h = models.PositiveIntegerField(default=0, verbose_name='Hits (H)')
    h2 = models.PositiveIntegerField(default=0, verbose_name='Dobles (2B)')
    h3 = models.PositiveIntegerField(default=0, verbose_name='Triples (3B)')
    hr = models.PositiveIntegerField(default=0, verbose_name='Jonrones (HR)')
    rbi = models.PositiveIntegerField(default=0, verbose_name='Carreras impulsadas (CI)')
    sb = models.PositiveIntegerField(default=0, verbose_name='Robadas (SB, en desuso)')
    bb = models.PositiveIntegerField(default=0, verbose_name='Boletos (BB)')
    hbp = models.PositiveIntegerField(default=0, verbose_name='Golpeados (HBP)')
    sf = models.PositiveIntegerField(default=0, verbose_name='Sacrificios (SF)')
    k = models.PositiveIntegerField(default=0, verbose_name='Ponches (K)')
    class Meta:
        unique_together = [('jugador', 'torneo')]
    @property
    def avg(self): return round(self.h / self.ab, 3) if self.ab else 0
    @property
    def tb(self): return (self.h - self.h2 - self.h3 - self.hr) + 2 * self.h2 + 3 * self.h3 + 4 * self.hr
    @property
    def obp(self):
        d = self.ab + self.bb + self.hbp + self.sf
        return round((self.h + self.bb + self.hbp) / d, 3) if d else 0
    @property
    def slg(self): return round(self.tb / self.ab, 3) if self.ab else 0
    @property
    def ops(self): return round(self.obp + self.slg, 3)
    def __str__(self): return f"{self.jugador} en {self.torneo}"


class ActuacionPitcheo(models.Model):
    """Línea de pitcheo por torneo. K = ponches propinados."""
    jugador = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='pitcheo')
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='pitcheo')
    jl = models.PositiveIntegerField(default=0, verbose_name='Juegos lanzados')
    ip_outs = models.PositiveIntegerField(default=0, verbose_name='Outs registrados')
    k = models.PositiveIntegerField(default=0, verbose_name='Ponches (K)')
    bb = models.PositiveIntegerField(default=0, verbose_name='Boletos')
    h = models.PositiveIntegerField(default=0, verbose_name='Hits permitidos')
    r = models.PositiveIntegerField(default=0, verbose_name='Carreras')
    er = models.PositiveIntegerField(default=0, verbose_name='Limpias')
    class Meta:
        unique_together = [('jugador', 'torneo')]
    @property
    def ip(self):
        return f"{self.ip_outs // 3}.{self.ip_outs % 3}"
    @property
    def era(self):
        ip = self.ip_outs / 3 if self.ip_outs else 0
        return round(self.er * 7 / ip, 2) if ip else 0
    def __str__(self): return f"{self.jugador} PIT en {self.torneo}"
