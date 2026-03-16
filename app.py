import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify

AR = ZoneInfo("America/Argentina/Buenos_Aires")
from database import (
    get_conn, init_db,
    create_session_with_date, log_exercise, update_exercise,
    delete_session, delete_exercise,
    get_all_foods, add_food, update_food, delete_food,
    log_food_with_date, get_food_logs_by_date, update_food_log, delete_food_log,
    get_food_week_summary,
    get_all_recipes, get_recipe, create_recipe, update_recipe, delete_recipe,
)
from exercises import WORKOUTS
from exercise_library import EXERCISE_LIBRARY, CATEGORY_INFO, DIFFICULTY_COLORS

app = Flask(__name__)


# ── Helpers gym ───────────────────────────────────────────────────────────────

def get_all_users():
    with get_conn() as conn:
        rows = conn.execute('SELECT telegram_id, name FROM users ORDER BY name').fetchall()
        return [{'id': r[0], 'name': r[1]} for r in rows]


def get_user_stats(user_id):
    with get_conn() as conn:
        total = conn.execute('SELECT COUNT(*) FROM sessions WHERE user_id = ?', (user_id,)).fetchone()[0]
        by_type = conn.execute(
            'SELECT day_type, COUNT(*) FROM sessions WHERE user_id = ? GROUP BY day_type', (user_id,)
        ).fetchall()
        return {'total': total, 'by_type': {r[0]: r[1] for r in by_type}}


def get_full_history(user_id):
    with get_conn() as conn:
        sessions = conn.execute(
            'SELECT id, day_type, date FROM sessions WHERE user_id = ? ORDER BY date DESC, id DESC',
            (user_id,)
        ).fetchall()
        result = []
        for session_id, day_type, date in sessions:
            exercises = conn.execute(
                'SELECT id, exercise_name, weights, note FROM exercise_logs WHERE session_id = ?',
                (session_id,)
            ).fetchall()
            result.append({
                'id': session_id, 'day_type': day_type, 'date': date,
                'title': WORKOUTS.get(day_type, {}).get('title', day_type.upper()),
                'emoji': WORKOUTS.get(day_type, {}).get('emoji', '🏋️'),
                'exercises': [
                    {'id': r[0], 'name': r[1], 'weights': json.loads(r[2]), 'note': r[3]}
                    for r in exercises
                ]
            })
        return result


def get_prs(user_id):
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


# ── Vista principal ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    init_db()
    users = get_all_users()
    user_data = []
    for user in users:
        uid = user['id']
        user_data.append({
            'id': uid, 'name': user['name'],
            'history': get_full_history(uid),
            'prs': get_prs(uid),
            'stats': get_user_stats(uid),
        })
    exercises_by_day = {k: [e['name'] for e in v['exercises']] for k, v in WORKOUTS.items()}
    foods = get_all_foods()
    recipes = get_all_recipes()
    return render_template('index.html', users=user_data, workouts=WORKOUTS,
                           exercises_by_day=exercises_by_day, foods=foods,
                           recipes=recipes,
                           exercise_library=EXERCISE_LIBRARY,
                           category_info=CATEGORY_INFO,
                           difficulty_colors=DIFFICULTY_COLORS)


# ── API Gym ───────────────────────────────────────────────────────────────────

@app.route('/api/session', methods=['POST'])
def api_create_session():
    data = request.json
    user_id, day_type, date = data.get('user_id'), data.get('day_type'), data.get('date')
    if not all([user_id, day_type, date]):
        return jsonify({'error': 'Faltan campos'}), 400
    session_id = create_session_with_date(user_id, day_type, date)
    return jsonify({'session_id': session_id})


@app.route('/api/session/<int:session_id>/exercise', methods=['POST'])
def api_add_exercise(session_id):
    data = request.json
    name, raw, note = data.get('name', '').strip(), data.get('weights', '').strip(), data.get('note', '')
    if not name or not raw:
        return jsonify({'error': 'Faltan campos'}), 400
    log_exercise(session_id, name, _parse_weights(raw), note)
    return jsonify({'ok': True})


@app.route('/api/exercise/<int:log_id>', methods=['PUT'])
def api_update_exercise(log_id):
    data = request.json
    raw = data.get('weights', '').strip()
    if not raw:
        return jsonify({'error': 'Pesos vacíos'}), 400
    update_exercise(log_id, _parse_weights(raw), data.get('note', ''))
    return jsonify({'ok': True})


@app.route('/api/exercise/<int:log_id>', methods=['DELETE'])
def api_delete_exercise(log_id):
    delete_exercise(log_id)
    return jsonify({'ok': True})


@app.route('/api/session/<int:session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    delete_session(session_id)
    return jsonify({'ok': True})


# ── API Comidas (logs) ────────────────────────────────────────────────────────

@app.route('/api/food-logs')
def api_food_logs():
    user_id = request.args.get('user_id', type=int)
    date = request.args.get('date', '')
    if not user_id or not date:
        return jsonify({'error': 'Faltan parámetros'}), 400
    logs = get_food_logs_by_date(user_id, date)
    return jsonify(logs)


@app.route('/api/food-log', methods=['POST'])
def api_add_food_log():
    data = request.json
    user_id   = data.get('user_id')
    food_name = data.get('food_name', '').strip()
    qty       = data.get('quantity_g', 0)
    kcal      = data.get('kcal', 0)
    protein   = data.get('protein', 0)
    fat       = data.get('fat', 0)
    carbs     = data.get('carbs', 0)
    meal_type = data.get('meal_type', 'general')
    date      = data.get('date', '')
    if not all([user_id, food_name, qty, date]):
        return jsonify({'error': 'Faltan campos'}), 400
    log_id = log_food_with_date(user_id, food_name, qty, kcal, protein, fat, carbs, meal_type, date)
    return jsonify({'log_id': log_id})


@app.route('/api/food-log/<int:log_id>', methods=['PUT'])
def api_update_food_log(log_id):
    data = request.json
    update_food_log(log_id, data['quantity_g'], data['kcal'],
                    data['protein'], data['fat'], data['carbs'], data['meal_type'])
    return jsonify({'ok': True})


@app.route('/api/food-log/<int:log_id>', methods=['DELETE'])
def api_delete_food_log(log_id):
    delete_food_log(log_id)
    return jsonify({'ok': True})


# ── API Biblioteca ────────────────────────────────────────────────────────────

@app.route('/api/food', methods=['POST'])
def api_add_food():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Nombre requerido'}), 400
    food_id = add_food(name, data.get('kcal', 0), data.get('protein', 0),
                       data.get('fat', 0), data.get('carbs', 0))
    return jsonify({'food_id': food_id})


@app.route('/api/food/<int:food_id>', methods=['PUT'])
def api_update_food(food_id):
    data = request.json
    update_food(food_id, data['name'], data['kcal'], data['protein'], data['fat'], data['carbs'])
    return jsonify({'ok': True})


@app.route('/api/food/<int:food_id>', methods=['DELETE'])
def api_delete_food_item(food_id):
    delete_food(food_id)
    return jsonify({'ok': True})


@app.route('/api/foods')
def api_list_foods():
    return jsonify(get_all_foods())


# ── API Recetas ───────────────────────────────────────────────────────────────

@app.route('/api/recipe', methods=['POST'])
def api_create_recipe():
    data = request.json
    name = data.get('name', '').strip()
    ingredients = data.get('ingredients', [])
    if not name or not ingredients:
        return jsonify({'error': 'Nombre e ingredientes requeridos'}), 400
    recipe_id = create_recipe(name, ingredients, servings=data.get('servings', 1))
    return jsonify({'recipe_id': recipe_id})


@app.route('/api/recipe/<int:recipe_id>', methods=['GET'])
def api_get_recipe(recipe_id):
    recipe = get_recipe(recipe_id)
    if not recipe:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(recipe)


@app.route('/api/recipe/<int:recipe_id>', methods=['PUT'])
def api_update_recipe(recipe_id):
    data = request.json
    name = data.get('name', '').strip()
    ingredients = data.get('ingredients', [])
    if not name or not ingredients:
        return jsonify({'error': 'Nombre e ingredientes requeridos'}), 400
    update_recipe(recipe_id, name, ingredients, servings=data.get('servings', 1))
    return jsonify({'ok': True})


@app.route('/api/recipe/<int:recipe_id>', methods=['DELETE'])
def api_delete_recipe(recipe_id):
    delete_recipe(recipe_id)
    return jsonify({'ok': True})


@app.route('/api/food-week')
def api_food_week():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'user_id requerido'}), 400
    today = datetime.now(AR).date()
    start = today - timedelta(days=6)
    data = get_food_week_summary(user_id, start.strftime('%Y-%m-%d'))
    # Rellenar días sin datos con 0
    day_map = {d['date']: d for d in data}
    result = []
    for i in range(6, -1, -1):
        day = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        result.append(day_map.get(day, {'date': day, 'kcal': 0, 'protein': 0}))
    return jsonify({'data': result, 'today': today.strftime('%Y-%m-%d')})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_weights(raw: str) -> list:
    weights = []
    for p in raw.replace('/', ' ').split():
        p = p.replace(',', '.')
        try:
            weights.append(float(p) if '.' in p else int(p))
        except ValueError:
            weights.append(p.upper())
    return weights


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"✅ Dashboard en http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
