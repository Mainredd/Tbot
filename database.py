import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

# En Railway: setear env var DB_PATH=/data/gym_tracker.db (volume montado en /data)
# En local: usa la carpeta del script automáticamente
DB_PATH = Path(os.environ.get('DB_PATH', str(Path(__file__).parent / 'gym_tracker.db')))

SEED_FOODS = [
    ('Pechuga de pollo', 165, 31.0, 3.6, 0.0),
    ('Carne vacuna', 250, 26.0, 15.0, 0.0),
    ('Salmón', 208, 20.0, 13.0, 0.0),
    ('Atún en lata', 116, 26.0, 1.0, 0.0),
    ('Huevo entero', 155, 13.0, 11.0, 1.1),
    ('Clara de huevo', 52, 11.0, 0.2, 0.7),
    ('Arroz blanco cocido', 130, 2.7, 0.3, 28.0),
    ('Arroz integral cocido', 123, 2.7, 1.0, 25.0),
    ('Avena', 389, 17.0, 7.0, 66.0),
    ('Pasta cocida', 131, 5.0, 1.1, 25.0),
    ('Papa cocida', 87, 1.9, 0.1, 20.0),
    ('Batata cocida', 86, 1.6, 0.1, 20.0),
    ('Pan integral', 247, 13.0, 3.4, 41.0),
    ('Pan blanco', 265, 9.0, 3.2, 49.0),
    ('Leche entera', 61, 3.2, 3.3, 4.8),
    ('Leche descremada', 34, 3.4, 0.1, 5.0),
    ('Yogur griego', 59, 10.0, 0.4, 3.6),
    ('Queso mozzarella', 280, 28.0, 17.0, 2.2),
    ('Queso cottage', 98, 11.0, 4.3, 3.4),
    ('Banana', 89, 1.1, 0.3, 23.0),
    ('Manzana', 52, 0.3, 0.2, 14.0),
    ('Naranja', 47, 0.9, 0.1, 12.0),
    ('Brócoli', 34, 2.8, 0.4, 7.0),
    ('Zanahoria', 41, 0.9, 0.2, 10.0),
    ('Tomate', 18, 0.9, 0.2, 3.9),
    ('Espinaca', 23, 2.9, 0.4, 3.6),
    ('Aceite de oliva', 884, 0.0, 100.0, 0.0),
    ('Manteca', 717, 0.9, 81.0, 0.1),
    ('Proteína whey', 400, 80.0, 5.0, 10.0),
    ('Maní', 567, 26.0, 49.0, 16.0),
    ('Almendras', 579, 21.0, 50.0, 22.0),
]


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                day_type TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS exercise_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                weights TEXT NOT NULL,
                note TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                kcal REAL NOT NULL DEFAULT 0,
                protein REAL NOT NULL DEFAULT 0,
                fat REAL NOT NULL DEFAULT 0,
                carbs REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS food_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                food_name TEXT NOT NULL,
                quantity_g REAL NOT NULL,
                kcal REAL NOT NULL DEFAULT 0,
                protein REAL NOT NULL DEFAULT 0,
                fat REAL NOT NULL DEFAULT 0,
                carbs REAL NOT NULL DEFAULT 0,
                meal_type TEXT DEFAULT 'general',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        ''')
    _seed_foods()
    apply_seed_sql()


def _seed_foods():
    """Corre UNA SOLA VEZ en toda la vida del DB (flag en tabla meta).
    Si el usuario borra alimentos, no vuelven a aparecer en el próximo restart."""
    with get_conn() as conn:
        already = conn.execute(
            "SELECT value FROM meta WHERE key='foods_seeded'"
        ).fetchone()
        if already:
            return  # Ya se ejecutó alguna vez → no tocar nada
        conn.executemany(
            'INSERT OR IGNORE INTO foods (name, kcal, protein, fat, carbs) VALUES (?,?,?,?,?)',
            SEED_FOODS
        )
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('foods_seeded', '1')")


def apply_seed_sql():
    """Aplica seed.sql si existe y la tabla users está vacía (primera vez en Railway)."""
    seed_file = Path(__file__).parent / 'seed.sql'
    if not seed_file.exists():
        return
    with get_conn() as conn:
        count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if count > 0:
            return  # Ya hay datos, no hacer nada
        sql = seed_file.read_text(encoding='utf-8')
        conn.executescript(sql)
        import logging
        logging.info(f"✅ seed.sql aplicado correctamente")


# ── Usuarios ──────────────────────────────────────────────────────────────────

def get_user(telegram_id):
    with get_conn() as conn:
        row = conn.execute(
            'SELECT telegram_id, name FROM users WHERE telegram_id = ?', (telegram_id,)
        ).fetchone()
        return {'id': row[0], 'name': row[1]} if row else None


def create_user(telegram_id, name):
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO users (telegram_id, name) VALUES (?, ?)', (telegram_id, name)
        )


# ── Sesiones de gym ───────────────────────────────────────────────────────────

def create_session(user_id, day_type):
    with get_conn() as conn:
        date = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.execute(
            'INSERT INTO sessions (user_id, day_type, date) VALUES (?, ?, ?)',
            (user_id, day_type, date)
        )
        return cursor.lastrowid


def create_session_with_date(user_id, day_type, date):
    with get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO sessions (user_id, day_type, date) VALUES (?, ?, ?)',
            (user_id, day_type, date)
        )
        return cursor.lastrowid


def log_exercise(session_id, exercise_name, weights, note=''):
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO exercise_logs (session_id, exercise_name, weights, note) VALUES (?, ?, ?, ?)',
            (session_id, exercise_name, json.dumps(weights), note)
        )


def update_exercise(log_id, weights, note=''):
    with get_conn() as conn:
        conn.execute(
            'UPDATE exercise_logs SET weights = ?, note = ? WHERE id = ?',
            (json.dumps(weights), note, log_id)
        )


def delete_session(session_id):
    with get_conn() as conn:
        conn.execute('DELETE FROM exercise_logs WHERE session_id = ?', (session_id,))
        conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))


def delete_exercise(log_id):
    with get_conn() as conn:
        conn.execute('DELETE FROM exercise_logs WHERE id = ?', (log_id,))


def get_pr(user_id, exercise_name):
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT el.weights FROM exercise_logs el
            JOIN sessions s ON el.session_id = s.id
            WHERE s.user_id = ? AND el.exercise_name = ?
        ''', (user_id, exercise_name)).fetchall()
    max_weight = 0.0
    for (weights_json,) in rows:
        for w in json.loads(weights_json):
            try:
                val = float(str(w).replace(',', '.'))
                if val > max_weight:
                    max_weight = val
            except (ValueError, TypeError):
                pass
    return max_weight if max_weight > 0 else None


def get_last_session(user_id, day_type):
    with get_conn() as conn:
        row = conn.execute('''
            SELECT id, date FROM sessions
            WHERE user_id = ? AND day_type = ?
            ORDER BY created_at DESC LIMIT 1 OFFSET 1
        ''', (user_id, day_type)).fetchone()
        if not row:
            return None
        session_id, date = row
        exercises = conn.execute(
            'SELECT exercise_name, weights, note FROM exercise_logs WHERE session_id = ?',
            (session_id,)
        ).fetchall()
        return {
            'date': date,
            'exercises': [
                {'name': r[0], 'weights': json.loads(r[1]), 'note': r[2]}
                for r in exercises
            ]
        }


def get_history(user_id, day_type, limit=3):
    with get_conn() as conn:
        sessions = conn.execute('''
            SELECT id, date FROM sessions
            WHERE user_id = ? AND day_type = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, day_type, limit)).fetchall()
        result = []
        for session_id, date in sessions:
            exercises = conn.execute(
                'SELECT exercise_name, weights, note FROM exercise_logs WHERE session_id = ?',
                (session_id,)
            ).fetchall()
            result.append({
                'date': date,
                'exercises': [
                    {'name': r[0], 'weights': json.loads(r[1]), 'note': r[2]}
                    for r in exercises
                ]
            })
        return result


def get_all_prs(user_id):
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT el.exercise_name, el.weights FROM exercise_logs el
            JOIN sessions s ON el.session_id = s.id WHERE s.user_id = ?
        ''', (user_id,)).fetchall()
    prs = {}
    for exercise_name, weights_json in rows:
        for w in json.loads(weights_json):
            try:
                val = float(str(w).replace(',', '.'))
                if exercise_name not in prs or val > prs[exercise_name]:
                    prs[exercise_name] = val
            except (ValueError, TypeError):
                pass
    return prs


# ── Biblioteca de alimentos ───────────────────────────────────────────────────

def get_all_foods():
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT id, name, kcal, protein, fat, carbs FROM foods ORDER BY name'
        ).fetchall()
        return [{'id': r[0], 'name': r[1], 'kcal': r[2], 'protein': r[3], 'fat': r[4], 'carbs': r[5]} for r in rows]


def _food_row(row):
    return {'id': row[0], 'name': row[1], 'kcal': row[2], 'protein': row[3], 'fat': row[4], 'carbs': row[5]}


def get_food_by_name(name: str):
    q = name.lower().strip()
    with get_conn() as conn:
        def search(pattern):
            return conn.execute(
                'SELECT id, name, kcal, protein, fat, carbs FROM foods WHERE LOWER(name) LIKE ?',
                (pattern,)
            ).fetchone()

        # 1. Exact match
        row = conn.execute(
            'SELECT id, name, kcal, protein, fat, carbs FROM foods WHERE LOWER(name) = ?', (q,)
        ).fetchone()
        if row:
            return _food_row(row)

        # 2. Query es substring del nombre ("huevo" → "Huevo entero")
        row = search(f'%{q}%')
        if row:
            return _food_row(row)

        # 3. Singular: quitar 's' final ("huevos" → "huevo" → "Huevo entero")
        if q.endswith('s') and len(q) > 3:
            row = search(f'%{q[:-1]}%')
            if row:
                return _food_row(row)

        # 4. Quitar 'es' final ("tomates" → "tomat" no, pero "filetes" → "filete")
        if q.endswith('es') and len(q) > 4:
            row = search(f'%{q[:-2]}%')
            if row:
                return _food_row(row)

        # 5. Para frases multi-palabra: todas las palabras deben estar (AND)
        words = [w for w in q.split() if len(w) > 3]
        if len(words) > 1:
            # Construir variantes singulares
            def variants(w):
                v = [w]
                if w.endswith('s') and len(w) > 4:
                    v.append(w[:-1])
                if w.endswith('es') and len(w) > 5:
                    v.append(w[:-2])
                return v

            # Buscar nombre que contenga TODAS las palabras (o sus singulares)
            all_foods = conn.execute(
                'SELECT id, name, kcal, protein, fat, carbs FROM foods'
            ).fetchall()
            for food_row in all_foods:
                fname = food_row[1].lower()
                if all(any(v in fname for v in variants(w)) for w in words):
                    return _food_row(food_row)

        # 6. Fallback: solo para queries de UNA palabra significativa
        if len(words) == 1:
            word = words[0]
            row = search(f'%{word}%')
            if row:
                return _food_row(row)
            if word.endswith('s') and len(word) > 4:
                row = search(f'%{word[:-1]}%')
                if row:
                    return _food_row(row)

    return None


def get_food_exact(name: str):
    """Match exacto o frase completa como substring. No parte por palabras."""
    q = name.lower().strip()
    with get_conn() as conn:
        # 1. Exact match
        row = conn.execute(
            'SELECT id, name, kcal, protein, fat, carbs FROM foods WHERE LOWER(name) = ?', (q,)
        ).fetchone()
        if row:
            return _food_row(row)
        # 2. La frase completa es substring del nombre en DB (o viceversa)
        row = conn.execute(
            'SELECT id, name, kcal, protein, fat, carbs FROM foods WHERE LOWER(name) LIKE ?',
            (f'%{q}%',)
        ).fetchone()
        if row:
            return _food_row(row)
    return None


def add_food(name, kcal, protein, fat, carbs):
    with get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO foods (name, kcal, protein, fat, carbs) VALUES (?, ?, ?, ?, ?)',
            (name, kcal, protein, fat, carbs)
        )
        return cursor.lastrowid


def update_food(food_id, name, kcal, protein, fat, carbs):
    with get_conn() as conn:
        conn.execute(
            'UPDATE foods SET name=?, kcal=?, protein=?, fat=?, carbs=? WHERE id=?',
            (name, kcal, protein, fat, carbs, food_id)
        )


def delete_food(food_id):
    with get_conn() as conn:
        conn.execute('DELETE FROM foods WHERE id = ?', (food_id,))


# ── Registro de comidas ───────────────────────────────────────────────────────

def log_food(user_id, food_name, quantity_g, kcal, protein, fat, carbs, meal_type='general'):
    with get_conn() as conn:
        date = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.execute(
            '''INSERT INTO food_logs (user_id, date, food_name, quantity_g, kcal, protein, fat, carbs, meal_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, date, food_name, quantity_g, kcal, protein, fat, carbs, meal_type)
        )
        return cursor.lastrowid


def log_food_with_date(user_id, food_name, quantity_g, kcal, protein, fat, carbs, meal_type, date):
    with get_conn() as conn:
        cursor = conn.execute(
            '''INSERT INTO food_logs (user_id, date, food_name, quantity_g, kcal, protein, fat, carbs, meal_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, date, food_name, quantity_g, kcal, protein, fat, carbs, meal_type)
        )
        return cursor.lastrowid


def get_food_logs_by_date(user_id, date):
    with get_conn() as conn:
        rows = conn.execute(
            '''SELECT id, food_name, quantity_g, kcal, protein, fat, carbs, meal_type
               FROM food_logs WHERE user_id = ? AND date = ? ORDER BY created_at''',
            (user_id, date)
        ).fetchall()
        return [
            {'id': r[0], 'food_name': r[1], 'quantity_g': r[2],
             'kcal': r[3], 'protein': r[4], 'fat': r[5], 'carbs': r[6], 'meal_type': r[7]}
            for r in rows
        ]


def update_food_log(log_id, quantity_g, kcal, protein, fat, carbs, meal_type):
    with get_conn() as conn:
        conn.execute(
            'UPDATE food_logs SET quantity_g=?, kcal=?, protein=?, fat=?, carbs=?, meal_type=? WHERE id=?',
            (quantity_g, kcal, protein, fat, carbs, meal_type, log_id)
        )


def delete_food_log(log_id):
    with get_conn() as conn:
        conn.execute('DELETE FROM food_logs WHERE id = ?', (log_id,))


def get_last_food_log(user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            '''SELECT id, food_name, quantity_g, kcal, meal_type FROM food_logs
               WHERE user_id = ? ORDER BY id DESC LIMIT 1''',
            (user_id,)
        ).fetchone()
        if row:
            return {'id': row[0], 'food_name': row[1], 'quantity_g': row[2],
                    'kcal': row[3], 'meal_type': row[4]}
    return None


def get_food_week_summary(user_id: int, start_date: str):
    """Retorna totales de kcal y proteínas agrupados por día, desde start_date."""
    with get_conn() as conn:
        rows = conn.execute(
            '''SELECT date, SUM(kcal), SUM(protein) FROM food_logs
               WHERE user_id = ? AND date >= ? GROUP BY date ORDER BY date''',
            (user_id, start_date)
        ).fetchall()
        return [{'date': r[0], 'kcal': round(r[1], 1), 'protein': round(r[2], 1)}
                for r in rows]
