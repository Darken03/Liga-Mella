from django.db import migrations


REGLAS = [
    (
        "El objetivo del juego",
        "Gana el equipo que anote más carreras al final del partido. "
        "El partido se juega a 7 innings: cada equipo batea en su turno y "
        "defiende en el otro. La visita batea en la parte alta y el local en la baja.",
        1,
    ),
    (
        "10 jugadores a la defensa: 4 jardineros",
        "En nuestra liga cada equipo defiende con 10 jugadores: pitcher (P), "
        "catcher (C), primera (1B), segunda (2B), shortstop (SS) y tercera (3B), "
        "más 4 jardineros: left field (LF), left-center (LCF), right-center (RCF) "
        "y right field (RF). Al bate se permite hasta 15 jugadores en el orden; "
        "los que no defienden quedan como extra hitters (EH).",
        2,
    ),
    (
        "No se permite el robo de bases",
        "El corredor debe permanecer en su base hasta que la bola sea bateada: "
        "no puede adelantar ni robar la siguiente base con el pitcher en acción. "
        "Solo avanza por batazos, bases por bola, golpeados o errores defensivos. "
        "Por eso las bases robadas (SB) no cuentan en las estadísticas.",
        3,
    ),
    (
        "Conteo, strikes y outs",
        "El conteo es de 4 bolas y 3 strikes: con 4 bolas el bateador va a primera, "
        "con 3 strikes es ponche (K). Con 3 outs se termina el turno y los equipos "
        "cambian de rol. El orden al bate se respeta y rota durante todo el juego.",
        4,
    ),
    (
        "Carreras impulsadas (CI)",
        "Las carreras que un bateador produce con su batazo se anotan como "
        "carreras impulsadas (CI). Un jonrón (HR) suma automáticamente la carrera "
        "del bateador más las impulsadas según los corredores en base.",
        5,
    ),
    (
        "Clasificación y playoffs",
        "La tabla se ordena por juegos ganados, diferencia de carreras (DIF) y "
        "carreras anotadas. Al terminar la fase regular, los 4 primeros clasifican: "
        "el 1° juega semifinal contra el 4° y el 2° contra el 3°. "
        "Los dos ganadores disputan la final. Los playoffs los activa la "
        "administración cuando la fase regular termina.",
        6,
    ),
]


def cargar_reglas(apps, schema_editor):
    Regla = apps.get_model("core", "Regla")
    if Regla.objects.exists():
        return
    for titulo, contenido, orden in REGLAS:
        Regla.objects.create(titulo=titulo, contenido=contenido, orden=orden, activa=True)


def quitar_reglas(apps, schema_editor):
    Regla = apps.get_model("core", "Regla")
    titulos = [t for t, _, _ in REGLAS]
    Regla.objects.filter(titulo__in=titulos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_regla"),
    ]

    operations = [
        migrations.RunPython(cargar_reglas, quitar_reglas),
    ]
