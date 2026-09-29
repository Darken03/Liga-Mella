"""Reglas oficiales del softball (base: reglamento WBSC) sin tocar las de la liga.

Se agregan después de las reglas propias (orden 7 en adelante) y solo si no
existen, para no duplicar ni alterar lo ya publicado.
"""

from django.db import migrations


REGLAS = [
    (
        "Juego reglamentario y entradas extras",
        "El partido oficial es a 7 innings, con 3 outs por turno. Si hay empate "
        "al cerrar el séptimo, se juegan entradas extras hasta desempatar. "
        "Un juego suspendido por lluvia, oscuridad u otra causa es válido desde "
        "el quinto inning (o si el local ya va ganando); si termina empatado "
        "tras 5 o más innings, se declara empate reglamentario.",
        7,
    ),
    (
        "Diferencia de carreras (nocaut)",
        "El juego termina anticipado si un equipo aventaja por 15 carreras tras "
        "3 innings, por 10 tras 4 innings o por 7 tras 5 innings, dándole "
        "siempre al local su turno al bate si aún puede definir.",
        8,
    ),
    (
        "Strikes, fouls y ponche",
        "Es strike: el pitcheo que pasa por la zona sin swing, el swing fallido "
        "y el foul (incluido con dos strikes). El foul tip atrapado con dos "
        "strikes es el tercer strike: el bateador es out. No se puede batear "
        "legalmente una bola que pique en el suelo antes del home.",
        9,
    ),
    (
        "Orden al bate y bateo fuera de turno",
        "El orden al bate se respeta durante todo el juego. Si un jugador batea "
        "fuera de turno y el contrario apela a tiempo, se marca out al que le "
        "tocaba batear y se anula lo que avanzaron los corredores en esa jugada.",
        10,
    ),
    (
        "Cómo vale una carrera",
        "La carrera vale si el corredor toca primera, segunda, tercera y home en "
        "orden, antes del tercer out. No vale si el tercer out es: el bateador "
        "puesto out antes de llegar a primera, un out forzado, o un corredor "
        "que salió de su base antes de tiempo.",
        11,
    ),
    (
        "Corredores: pisar, no rebasar y retocar",
        "Todo corredor debe pisar las bases en orden y no puede rebasar al "
        "corredor que va delante. En un elevado atrapado de aire debe retocar "
        "su base (tag up) antes de correr; si sale antes y hay apelación, es out.",
        12,
    ),
    (
        "Interferencia y obstrucción",
        "El corredor que estorba a un fildeador en acción de fildeo es out y la "
        "bola queda muerta. Al revés, si un fildeador bloquea al corredor sin "
        "tener la bola (obstrucción), el árbitro le concede la base afectada.",
        13,
    ),
    (
        "Bola viva y bola muerta",
        "Con jonrón fuera del parque, golpeado o bola bloqueada, los corredores "
        "avanzan las bases que conceda el árbitro. Con bola muerta nadie puede "
        "ser puesto out ni avanzar, salvo por concesión del árbitro.",
        14,
    ),
]

FUENTE = " — <em>Reglamento oficial WBSC.</em>"


def cargar_reglas(apps, schema_editor):
    Regla = apps.get_model("core", "Regla")
    existentes = set(Regla.objects.values_list("titulo", flat=True))
    for titulo, contenido, orden in REGLAS:
        if titulo in existentes:
            continue
        Regla.objects.create(
            titulo=titulo, contenido=contenido + FUENTE, orden=orden, activa=True)


def quitar_reglas(apps, schema_editor):
    Regla = apps.get_model("core", "Regla")
    titulos = [t for t, _, _ in REGLAS]
    Regla.objects.filter(titulo__in=titulos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_reglas_basicas"),
    ]

    operations = [
        migrations.RunPython(cargar_reglas, quitar_reglas),
    ]
