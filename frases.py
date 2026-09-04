"""Banco de frases random para darle personalidad a Draculin."""

import random

FRASES_VAMPIRICAS = [
    "La noche es joven, y vos también, chuladaaaa.",
    "El ajo aleja vampiros, no responsabilidades.",
    "Hasta un vampiro necesita organizarse antes del amanecer.",
    "El murciélago madruga, pero el vampiro planifica.",
    "No hay ataúd lo suficientemente cómodo para ignorar tus pendientes.",
    "Un gasto sin anotar es un fantasma que vuelve a asustarte a fin de mes.",
    "Los espejos no me reflejan, pero tus pendientes sí me los acuerdo todos.",
    "300 años de no muerto y todavía no invento excusa para no hacer la lista de tareas.",
    "Duermo en un ataúd, no en excusas.",
    "Mi capa no tiene bolsillos, por eso te insisto con anotar los gastos.",
    "Ni la cruz ni el agua bendita me asustan tanto como un mes sin presupuesto.",
    "Transilvania queda lejos, tus pendientes no.",
    "Colmillo afilado, agenda más afilada todavía.",
    "Un castillo lleno de telarañas es más ordenado que tu bandeja de pendientes.",
    "Chuparte la sangre no, pero recordarte tus tareas sí es lo mío.",
]

FRASES_CHISTOSAS = [
    "Dormir de día tiene sus ventajas: nadie te pide explicaciones.",
    "Si el WiFi se cae en tu cripta, ¿sigue siendo una emergencia sobrenatural?",
    "El colmo de un vampiro: que le digan 'te ves pálido' como si fuera novedad.",
    "Contar ovejas no funciona conmigo, prefiero contar tus gastos pendientes.",
    "No soy vago, estoy en modo murciélago de bajo consumo.",
    "Mi horóscopo de hoy: 'evitá el sol y las decisiones financieras apuradas'.",
    "Un café a las 3 AM y ya nos creemos productivos los dos.",
    "Si postergar fuera deporte olímpico, yo ya tendría medalla y vos también.",
    "Hay gente que cuenta ovejitas, yo cuento excusas para no ir al gimnasio.",
    "El bug no es un error, es una característica que todavía no explicamos bien.",
    "Mi relación con el ejercicio es a distancia, muy a distancia.",
    "Toda dieta empieza un lunes que nunca llega.",
    "El wifi de la casa de la abuela sigue siendo más rápido que la fibra óptica de algunos barrios.",
    "Si hablar solo fuera raro, yo ya sería el raro oficial de esta cripta.",
    "Cada vez que digo 'ya lo hago' pasan mínimo tres días.",
    "El autocorrector arruinó más amistades que cualquier chisme.",
    "Nadie más ansioso que yo esperando que cargue una barra de progreso al 99%.",
]

FRASES_FACTOS = [
    "Facto random: los pulpos tienen tres corazones, banda. Nosotros con uno ya hacemos drama.",
    "Facto random: las jirafas duermen como 2 horas por día. Y encima paradas.",
    "Facto random: la miel no se pudre nunca, tienen encontrado frascos de miles de años y todavía sirve.",
    "Facto random: los murciélagos no son ciegos, algunos ven mejor que nosotros de noche.",
    "Facto random: el corazón de una ballena azul pesa como un auto chico.",
    "Facto random: hay más estrellas en el universo que granos de arena en todas las playas juntas.",
    "Facto random: los pulpos pueden cambiar de color más rápido que vos de humor un lunes.",
    "Facto random: un día en Venus dura más que un año en Venus. Ahí sí que se complica la agenda.",
    "Facto random: las nutrias duermen tomadas de la mano para no separarse en el agua.",
    "Facto random: el corazón de un camarón está en su cabeza, banda.",
    "Facto random: los flamencos nacen grises, el rosado es por lo que comen.",
    "Facto random: la Antártida es técnicamente el desierto más grande del mundo.",
    "Facto random: los plátanos son técnicamente bayas, y las fresas no.",
    "Facto random: un grupo de cuervos se llama 'parlamento', casi tan ruidoso como uno de verdad.",
    "Facto random: el sonido no viaja en el espacio, ahí ni gritando te escuchan.",
    "Facto random: hay más árboles en la Tierra que estrellas en la Vía Láctea.",
    "Facto random: los koalas tienen huellas dactilares casi idénticas a las humanas.",
]

FRASES_MOTIVACIONALES = [
    "Un paso a la vez, aunque sea en la oscuridad, sigue siendo avanzar.",
    "No hace falta ver la luz del día para tener las cosas claras.",
    "Cada tarea tachada es una pequeña victoria, celebrala.",
    "Lo que hoy parece imposible, la próxima semana ya es rutina.",
    "Organizarte hoy es hacerle un favor a la persona que vas a ser mañana.",
    "No necesitás ser perfecto, necesitás ser constante.",
    "Hasta la noche más larga termina en amanecer, aunque a mí no me convenga decirlo.",
    "El progreso no siempre se ve, pero siempre se acumula.",
    "No compares tu capítulo 3 con el capítulo 20 de otro.",
    "Los días difíciles también cuentan como avance, aunque no lo sientas.",
    "Empezar mal es mejor que no empezar.",
    "La disciplina de hoy es la libertad de mañana.",
    "No se trata de tener tiempo, se trata de hacerle lugar a lo importante.",
    "Cada meta grande fue una lista de tareas chiquitas antes.",
    "Si ya llegaste hasta acá, ya demostraste que podés seguir.",
    "El cansancio es temporal, haber abandonado dura mucho más.",
]

FRASES_SENTIMENTALES = [
    "Cuidate, aunque sea yo el único que te lo recuerde hoy.",
    "Está bien no tener todo resuelto todavía, tomate tu tiempo.",
    "A veces el mayor logro del día es simplemente haber seguido adelante.",
    "Sos más fuerte de lo que un mal día te hace sentir.",
    "No estás solo en esto, aunque el que te acompañe sea un vampiro con un bot.",
    "Mereces descansar tanto como mereces cumplir tus metas.",
    "Un mensaje simple a veces alcanza para recordarte que importás.",
    "Está bien pedir ayuda, hasta yo tuve que aprender a delegar recordatorios.",
    "No todos los días van a ser productivos, y está bien.",
    "Sé amable con vos mismo, ya sos bastante duro cuando las cosas salen mal.",
    "El esfuerzo que nadie ve también cuenta, y mucho.",
    "A veces la victoria es simplemente no haberte rendido hoy.",
    "Tus ganas de mejorar ya dicen mucho de vos.",
    "No hace falta tenerlo todo resuelto para merecer un buen día.",
]

FRASES = (
    FRASES_VAMPIRICAS
    + FRASES_CHISTOSAS
    + FRASES_FACTOS
    + FRASES_MOTIVACIONALES
    + FRASES_SENTIMENTALES
)


def obtener_frase_random() -> str:
    return random.choice(FRASES)
