"""
Biblioteca de ejercicios con descripciones, músculos, tips y videos.
Cada ejercicio del plan PPL está documentado acá.
"""

EXERCISE_LIBRARY = {
    # ═══════════════════════════════════════════════════════════════════
    # PUSH — Pecho · Hombro · Tríceps
    # ═══════════════════════════════════════════════════════════════════
    'Press Banco Inclinado c/ Barra': {
        'muscles':     ['Pecho superior', 'Deltoides anterior', 'Tríceps'],
        'category':    'push',
        'equipment':   'Barra + banco inclinado',
        'difficulty':  'Intermedio',
        'description': 'Acostado en banco inclinado (30-45°), agarrá la barra un poco más ancho que los hombros. Bajá controlado hasta el pecho superior y empujá explosivo arriba.',
        'tips': [
            'Retracción escapular: juntá los omóplatos antes de levantar',
            'Ángulo ideal: 30° para más pecho, 45° involucra más hombro',
            'Los pies firmes en el piso, glúteos apretados contra el banco',
            'No rebotes la barra en el pecho',
        ],
        'video_query': 'incline barbell bench press form',
    },
    'Press Plano c/ Mancuernas': {
        'muscles':     ['Pecho medio', 'Deltoides anterior', 'Tríceps'],
        'category':    'push',
        'equipment':   'Mancuernas + banco plano',
        'difficulty':  'Intermedio',
        'description': 'Acostado en banco plano, una mancuerna en cada mano. Bajá abriendo los codos a 45° hasta que los brazos queden paralelos al piso, luego empujá juntando arriba.',
        'tips': [
            'Mayor rango de movimiento que la barra: aprovechá para bajar más',
            'Girá las muñecas levemente al subir para mayor contracción',
            'No choques las mancuernas arriba, dejá 2-3 cm entre ellas',
            'Controlá la bajada (2-3 seg excéntrico)',
        ],
        'video_query': 'dumbbell bench press form tips',
    },
    'Aperturas en Máquina': {
        'muscles':     ['Pecho (estiramiento)', 'Deltoides anterior'],
        'category':    'push',
        'equipment':   'Máquina pec deck',
        'difficulty':  'Principiante',
        'description': 'Sentado en la máquina pec deck, con los brazos a la altura del pecho. Juntá los brazos al frente apretando el pecho, volvé controlado.',
        'tips': [
            'Squeeze al final: mantené 1 seg la contracción al juntar',
            'No uses impulso, el movimiento es lento y controlado',
            'Codos ligeramente flexionados, nunca bloqueados',
            'Sentí el estiramiento al abrir, no vayas más allá del rango cómodo',
        ],
        'video_query': 'pec deck fly machine form',
    },
    'Press Militar c/ Mancuernas': {
        'muscles':     ['Deltoides anterior', 'Deltoides lateral', 'Tríceps'],
        'category':    'push',
        'equipment':   'Mancuernas + banco a 90°',
        'difficulty':  'Intermedio',
        'description': 'Sentado con respaldo a 90°, mancuernas a la altura de los hombros con palmas al frente. Empujá vertical hasta extender los brazos arriba.',
        'tips': [
            'No arquees la espalda baja, mantené el core apretado',
            'Bajá hasta que los codos estén a 90° o un poco más',
            'Trayectoria en arco: las mancuernas se acercan arriba',
            'Respirá: exhalá al empujar, inhalá al bajar',
        ],
        'video_query': 'seated dumbbell shoulder press form',
    },
    'Vuelos Laterales c/ Mancuernas': {
        'muscles':     ['Deltoides lateral'],
        'category':    'push',
        'equipment':   'Mancuernas',
        'difficulty':  'Principiante',
        'description': 'De pie, mancuernas a los costados. Levantá los brazos lateralmente hasta la altura de los hombros, codos ligeramente doblados. Bajá controlado.',
        'tips': [
            'Pensá en "volcar un vaso de agua" al subir (meñique arriba)',
            'No subas más allá de los hombros, genera impingement',
            'Usá peso liviano con buena forma, no balancees el cuerpo',
            'El codo siempre ligeramente más alto que la muñeca',
        ],
        'video_query': 'lateral raise form tips',
    },
    'Press Francés c/ Mancuernas': {
        'muscles':     ['Tríceps (cabeza larga)', 'Tríceps (cabeza lateral)'],
        'category':    'push',
        'equipment':   'Mancuernas + banco plano',
        'difficulty':  'Intermedio',
        'description': 'Acostado en banco, mancuernas extendidas arriba. Flexioná los codos bajando las mancuernas a los lados de la cabeza sin mover los brazos superiores. Extendé de vuelta.',
        'tips': [
            'Los codos apuntan al techo y NO se mueven, solo el antebrazo',
            'Bajá lento (3 seg), subí explosivo',
            'Usá agarre neutro (palmas enfrentadas) para menor estrés en muñecas',
            'No dejes que los codos se abran hacia afuera',
        ],
        'video_query': 'dumbbell skull crushers form',
    },
    'Extensión Polea Alta c/ Cuerda': {
        'muscles':     ['Tríceps (cabeza lateral)', 'Tríceps (cabeza medial)'],
        'category':    'push',
        'equipment':   'Polea alta + cuerda',
        'difficulty':  'Principiante',
        'description': 'De pie frente a la polea alta, agarrá la cuerda con ambas manos. Empujá hacia abajo extendiendo los codos, abriendo la cuerda al final del movimiento.',
        'tips': [
            'Codos pegados al cuerpo, solo se mueve el antebrazo',
            'Abrí la cuerda al final y hacé una pausa de 1 seg',
            'Torso levemente inclinado hacia adelante',
            'No uses el peso del cuerpo para bajar, solo los tríceps',
        ],
        'video_query': 'tricep rope pushdown form',
    },

    # ═══════════════════════════════════════════════════════════════════
    # PULL — Espalda · Bíceps
    # ═══════════════════════════════════════════════════════════════════
    'Dominadas': {
        'muscles':     ['Dorsal ancho', 'Romboides', 'Bíceps', 'Core'],
        'category':    'pull',
        'equipment':   'Barra de dominadas',
        'difficulty':  'Avanzado',
        'description': 'Colgado de la barra con agarre prono (palmas al frente), un poco más ancho que los hombros. Subí hasta que la barbilla supere la barra, bajá controlado.',
        'tips': [
            'Iniciá el movimiento bajando las escápulas, no tirando con los brazos',
            'Evitá el kipping (balanceo). Movimiento estricto',
            'Si no llegás a hacer varias, usá banda elástica de asistencia',
            'Bajada lenta (3 seg) para maximizar la activación',
        ],
        'video_query': 'pull up form tips strict',
    },
    'Jalón al Pecho': {
        'muscles':     ['Dorsal ancho', 'Romboides', 'Bíceps'],
        'category':    'pull',
        'equipment':   'Polea alta + barra ancha',
        'difficulty':  'Principiante',
        'description': 'Sentado en la máquina, agarrá la barra ancha con agarre prono. Tirá hacia el pecho sacando el pecho hacia afuera, apretando las escápulas atrás.',
        'tips': [
            'Sacá pecho y tirá los codos hacia abajo y atrás',
            'No tires la barra detrás de la nuca (riesgo de lesión)',
            'Controlá la subida, no dejes que el peso te tire',
            'Imaginá que querés meter los codos en los bolsillos traseros',
        ],
        'video_query': 'lat pulldown form tips',
    },
    'Remo': {
        'muscles':     ['Dorsal ancho', 'Romboides', 'Trapecio medio', 'Bíceps'],
        'category':    'pull',
        'equipment':   'Polea baja / máquina de remo',
        'difficulty':  'Intermedio',
        'description': 'Sentado con los pies en la plataforma, agarrá el mango. Tirá hacia el abdomen bajo sacando pecho y juntando escápulas. Volvé controlado estirando.',
        'tips': [
            'Remá con los codos, no con las manos',
            'Mantené la espalda recta, no te encorves',
            'Squeeze de 1 seg al final, juntando escápulas',
            'No uses impulso del torso, quedate relativamente quieto',
        ],
        'video_query': 'seated cable row form',
    },
    'Curl Bíceps c/ Barra Z': {
        'muscles':     ['Bíceps (cabeza corta y larga)', 'Braquial'],
        'category':    'pull',
        'equipment':   'Barra Z',
        'difficulty':  'Principiante',
        'description': 'De pie, agarrá la barra Z en los ángulos internos. Con los codos pegados al cuerpo, flexioná los brazos hasta arriba y bajá controlado.',
        'tips': [
            'Codos fijos a los costados, solo se mueve el antebrazo',
            'Sin balanceo del cuerpo, si necesitás impulso bajá el peso',
            'Bajada lenta y controlada (no dejes caer)',
            'La barra Z reduce estrés en las muñecas vs barra recta',
        ],
        'video_query': 'ez bar curl form tips',
    },
    'Curl Bíceps c/ Mancuerna': {
        'muscles':     ['Bíceps', 'Braquiorradial'],
        'category':    'pull',
        'equipment':   'Mancuernas',
        'difficulty':  'Principiante',
        'description': 'De pie o sentado, una mancuerna en cada mano. Flexioná alternando o ambos a la vez, rotando la muñeca (supinación) al subir.',
        'tips': [
            'Supinación completa: rotá la palma hacia arriba al subir',
            'No balancees, si el cuerpo se mueve el peso es excesivo',
            'Probá la variante concentrada apoyando el codo en la rodilla',
            'Squeeze arriba de 1 seg para mayor contracción',
        ],
        'video_query': 'dumbbell bicep curl form',
    },
    'Polea Bíceps 5×15×5×10': {
        'muscles':     ['Bíceps', 'Braquial', 'Antebrazo'],
        'category':    'pull',
        'equipment':   'Polea baja + barra recta',
        'difficulty':  'Avanzado',
        'description': 'Método de fatiga acumulada: 5 reps pesadas → sin descanso → 15 reps livianas → sin descanso → 5 pesadas → 10 medio. Un solo set brutal.',
        'tips': [
            'Prepará 2-3 pesos antes de empezar (pesado, liviano, medio)',
            'Sin descanso entre bloques, la fatiga es el objetivo',
            'Mantené la forma estricta incluso cuando fatigues',
            'Este ejercicio va al final del día de pull como finisher',
        ],
        'video_query': 'cable bicep curl drop set',
    },

    # ═══════════════════════════════════════════════════════════════════
    # LEGS — Piernas · Core
    # ═══════════════════════════════════════════════════════════════════
    'Peso Muerto': {
        'muscles':     ['Isquiotibiales', 'Glúteos', 'Erectores espinales', 'Core'],
        'category':    'legs',
        'equipment':   'Barra + discos',
        'difficulty':  'Avanzado',
        'description': 'De pie, barra en el piso frente a las canillas. Agarrá la barra, empujá el piso con los pies, extendé cadera y rodillas simultáneamente. La barra sube pegada al cuerpo.',
        'tips': [
            'Espalda NEUTRA siempre, nunca redondear la lumbar',
            'La barra se mueve en línea recta pegada a las piernas',
            'Empujá el piso, no tires con la espalda',
            'Bloqueá arriba apretando glúteos, no hiperextiendas',
        ],
        'video_query': 'deadlift form tips beginner',
    },
    'Sentadilla Hack / Libre': {
        'muscles':     ['Cuádriceps', 'Glúteos', 'Core'],
        'category':    'legs',
        'equipment':   'Máquina hack / barra',
        'difficulty':  'Intermedio',
        'description': 'En la máquina hack: apoyá la espalda en el respaldo, pies adelante a lo ancho de hombros. Bajá controlado hasta 90° o más y empujá subiendo.',
        'tips': [
            'Pies más arriba en la plataforma = más glúteo e isquio',
            'Pies más abajo = más cuádriceps',
            'Rodillas en la dirección de los pies, no hacia adentro',
            'Si es sentadilla libre: la barra va sobre los trapecios, no el cuello',
        ],
        'video_query': 'hack squat machine form',
    },
    'Hip Thrust': {
        'muscles':     ['Glúteo mayor', 'Glúteo medio', 'Isquiotibiales'],
        'category':    'legs',
        'equipment':   'Barra + banco',
        'difficulty':  'Intermedio',
        'description': 'Espalda superior apoyada en un banco, barra sobre la cadera (con pad). Bajá la cadera y empujá arriba apretando glúteos hasta quedar paralelo al piso.',
        'tips': [
            'Apretá los glúteos FUERTE arriba, pausa de 1 seg',
            'Barbilla al pecho al subir para mantener posición',
            'Pies separados a lo ancho de hombros, a ~30 cm del banco',
            'Usá un pad o toalla en la barra para proteger la cadera',
        ],
        'video_query': 'hip thrust form barbell',
    },
    'Camilla Cuádriceps': {
        'muscles':     ['Cuádriceps (recto femoral, vasto lateral, vasto medial)'],
        'category':    'legs',
        'equipment':   'Máquina de extensión',
        'difficulty':  'Principiante',
        'description': 'Sentado en la máquina, el rodillo detrás de los tobillos. Extendé las piernas hasta arriba, apretá 1 seg, y bajá controlado.',
        'tips': [
            'Pausa arriba de 1-2 seg para máxima contracción',
            'Bajada lenta y controlada (3 seg)',
            'No uses impulso al arrancar, empezá suave',
            'Ajustá el respaldo para que las rodillas queden alineadas con el eje de la máquina',
        ],
        'video_query': 'leg extension machine form',
    },
    'Camilla Isquios': {
        'muscles':     ['Isquiotibiales (bíceps femoral, semitendinoso)'],
        'category':    'legs',
        'equipment':   'Máquina de curl acostado',
        'difficulty':  'Principiante',
        'description': 'Acostado boca abajo, el rodillo sobre los talones. Flexioná las piernas trayendo los talones hacia los glúteos, bajá controlado.',
        'tips': [
            'Bajada LENTA (excéntrico 3 seg) para máxima activación',
            'No levantes la cadera de la máquina al subir',
            'Apretá al máximo arriba antes de bajar',
            'Pies en posición neutra (ni puntas ni talones)',
        ],
        'video_query': 'lying leg curl form',
    },
    'Gemelos / Aductores': {
        'muscles':     ['Gastrocnemio', 'Sóleo', 'Aductores'],
        'category':    'legs',
        'equipment':   'Máquina de gemelos / aductora',
        'difficulty':  'Principiante',
        'description': 'Gemelos: de pie o sentado, subí en puntas de pie y bajá estirando el talón por debajo de la plataforma. Aductores: sentado en la máquina, juntá las piernas.',
        'tips': [
            'Gemelos: rango completo, bajá TODO lo que puedas estirar',
            'Pausa arriba de 2 seg apretando fuerte',
            'Aductores: controlá la apertura, no dejes que te abra de golpe',
            'Alternó entre gemelos de pie (gastrocnemio) y sentado (sóleo)',
        ],
        'video_query': 'calf raise form tips',
    },
    'Abdominales (opcional)': {
        'muscles':     ['Recto abdominal', 'Oblicuos', 'Transverso'],
        'category':    'legs',
        'equipment':   'Peso corporal / polea',
        'difficulty':  'Principiante',
        'description': 'Variaciones: crunches en piso, plancha, elevaciones de piernas colgado, o crunch en polea. Elegí 1-2 variantes por sesión.',
        'tips': [
            'Crunches: no tires del cuello, mirá al techo',
            'Plancha: cuerpo recto como una tabla, glúteos apretados',
            'Elevaciones: controlá la bajada, no dejes caer las piernas',
            'Exhalá fuerte al contraer para mayor activación',
        ],
        'video_query': 'ab exercises crunches plank',
    },
    'Lumbares (opcional)': {
        'muscles':     ['Erectores espinales', 'Multífidos'],
        'category':    'legs',
        'equipment':   'Banco de hiperextensiones / máquina',
        'difficulty':  'Principiante',
        'description': 'En banco de hiperextensiones, bajá el torso controlado y subí hasta quedar en línea recta con las piernas. No hiperextiendas.',
        'tips': [
            'No subas más allá de la línea neutra (no arquear atrás)',
            'Bajada controlada, subida con contracción',
            'Podés agregar peso (disco en el pecho) cuando sea fácil',
            'Excelente para prevenir dolor de espalda baja',
        ],
        'video_query': 'back extension hyperextension form',
    },
}

# Mapeo de categoría a info del workout
CATEGORY_INFO = {
    'push': {'emoji': '🏋️', 'title': 'PUSH · Pecho · Hombro · Tríceps', 'color': '#ff9800'},
    'pull': {'emoji': '💪', 'title': 'PULL · Espalda · Bíceps', 'color': '#4fc3f7'},
    'legs': {'emoji': '🦵', 'title': 'LEGS · Piernas · Core', 'color': '#c8ff00'},
}

# Colores para dificultad
DIFFICULTY_COLORS = {
    'Principiante': '#00e676',
    'Intermedio':   '#ff9800',
    'Avanzado':     '#ff4444',
}
