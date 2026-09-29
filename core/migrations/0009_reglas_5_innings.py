"""La liga juega a 5 innings (no 7) + doble por bola muerta en la calle.

Actualiza el contenido de esas reglas solo si aún tienen el texto original,
para no pisar ediciones hechas desde Administración.
"""

from django.db import migrations


CAMBIOS = [
    (
        "El objetivo del juego",
        "se juega a 7 innings",
        "Gana el equipo que anote más carreras al final del partido. "
        "El partido se juega a 5 innings: cada equipo batea en su turno y "
        "defiende en el otro. La visita batea en la parte alta y el local en la baja.",
    ),
    (
        "Juego reglamentario y entradas extras",
        "a 7 innings",
        "El partido oficial es a 5 innings, con 3 outs por turno. Si hay empate "
        "al cerrar el quinto, se juegan entradas extras hasta desempatar. "
        "Un juego suspendido por lluvia, oscuridad u otra causa es válido desde "
        "el tercer inning (o si el local ya va ganando); si termina empatado "
        "tras 3 o más innings, se declara empate reglamentario."
        " — <em>Reglamento oficial WBSC, adaptado a 5 innings.</em>",
    ),
    (
        "Diferencia de carreras (nocaut)",
        "15 carreras",
        "El juego termina anticipado si un equipo aventaja por 10 carreras tras "
        "3 innings o por 7 tras 4 innings, dándole siempre al local su turno "
        "al bate si aún puede definir."
        " — <em>Reglamento oficial WBSC, adaptado a 5 innings.</em>",
    ),
    (
        "Bola viva y bola muerta",
        "bola bloqueada, los corredores",
        "Con jonrón fuera del parque, golpeado o bola bloqueada, los corredores "
        "avanzan las bases que conceda el árbitro. Si un batazo de aire cae en "
        "la calle o en un lugar inaccesible para los fildeadores, es bola muerta "
        "y se concede doble: el bateador va a segunda y los corredores avanzan "
        "dos bases. Con bola muerta nadie puede ser puesto out ni avanzar, salvo "
        "por concesión del árbitro."
        " — <em>Reglamento oficial WBSC.</em>",
    ),
]


def aplicar(apps, schema_editor):
    Regla = apps.get_model("core", "Regla")
    for titulo, fragmento_viejo, nuevo in CAMBIOS:
        r = Regla.objects.filter(titulo=titulo).first()
        if r is not None and fragmento_viejo in (r.contenido or ""):
            r.contenido = nuevo
            r.save(update_fields=["contenido"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_reglas_oficiales_wbsc"),
    ]

    operations = [
        migrations.RunPython(aplicar, migrations.RunPython.noop),
    ]
