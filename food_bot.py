import logging
import os
import re
import json
import base64
import httpx
import anthropic
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv
import database as db

load_dotenv()
FOOD_TOKEN        = os.getenv('FOOD_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

ai = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
AR = ZoneInfo("America/Argentina/Buenos_Aires")

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

MEAL_EMOJIS = {
    'desayuno': '🌅', 'almuerzo': '☀️',
    'merienda': '🍎', 'cena': '🌙', 'general': '🍽',
}


# ── Claude: entender intent del mensaje ──────────────────────────────────────

async def understand_intent(text: str) -> dict | None:
    try:
        resp = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content":
                f"""Sos un asistente de nutrición. Analizá este mensaje y devolvé SOLO JSON sin markdown:
"{text}"

Detectá el intent:
- "log_food": registrar uno o más alimentos comidos. Extraé TODOS los ítems del mensaje.
- "add_to_library": agregar un alimento a la biblioteca. Estimá macros por 100g.
- "unknown": no es sobre comida.

Palabras clave add_to_library: "agrega", "agregá", "guardá", "guarda", "a la biblioteca", "en la biblioteca".

Conversiones:
- 1 huevo = 55g | 1 clara = 33g | 1 yema = 18g | 1 cucharada = 15g | 1 cucharadita = 5g
- 1 taza cereal/arroz/avena = 80g | 1 taza líquido = 240g | 1 vaso = 250g
- 1 rebanada pan = 30g | 1 banana = 120g | 1 manzana = 150g | 1 barra chocolate = 40g
- meal_type: detectá de contexto (desayuno/almuerzo/merienda/cena), si no → "general"

Respuesta JSON exacta:
{{"intent":"log_food|add_to_library|unknown","items":[{{"food_name":"nombre","quantity_g":0,"meal_type":"general"}}],"food_name":"","kcal":0,"protein":0,"fat":0,"carbs":0}}

- log_food: "items" tiene TODOS los alimentos del mensaje (1 o más líneas/ítems).
- add_to_library: "food_name" con el nombre, estimá kcal/protein/fat/carbs por 100g. items=[].
- Solo JSON válido, sin texto extra."""
            }]
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r'```json?\n?', '', raw).strip('`').strip()
        return json.loads(raw)
    except Exception as e:
        logging.error(f"Claude intent error: {e}")
        return None


# ── Claude: leer etiqueta nutricional ────────────────────────────────────────

async def read_label_with_claude(image_bytes: bytes) -> dict | None:
    try:
        img_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        resp = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=180,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text":
                    """Extraé la info nutricional de esta etiqueta. Devolvé SOLO JSON sin markdown:
{"food_name":"nombre del producto","kcal":0,"protein":0,"fat":0,"carbs":0}
- Todos los valores deben ser por 100g
- Si los valores son por porción, convertí a per 100g
- Solo JSON válido, sin texto extra"""
                }
            ]}]
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r'```json?\n?', '', raw).strip('`').strip()
        return json.loads(raw)
    except Exception as e:
        logging.error(f"Label read error: {e}")
        return None


# ── Open Food Facts ───────────────────────────────────────────────────────────

async def search_off(name: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": name, "search_simple": 1,
                    "action": "process", "json": 1, "page_size": 5,
                    "fields": "product_name,nutriments",
                }
            )
            for product in resp.json().get("products", []):
                n = product.get("nutriments", {})
                kcal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
                if kcal and float(kcal) > 0:
                    return {
                        "name":    product.get("product_name", name),
                        "kcal":    round(float(kcal), 1),
                        "protein": round(float(n.get("proteins_100g",       0)), 1),
                        "fat":     round(float(n.get("fat_100g",            0)), 1),
                        "carbs":   round(float(n.get("carbohydrates_100g",  0)), 1),
                    }
    except Exception as e:
        logging.error(f"OFF search error: {e}")
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def macros_line(kcal, protein, fat, carbs) -> str:
    return f"🔥 {kcal} kcal  |  🥩 {protein}g prot  |  🫒 {fat}g grasas  |  🍚 {carbs}g carbos"

def calc_macros(food: dict, qty: float) -> tuple:
    return (
        round(food['kcal']    * qty / 100, 1),
        round(food['protein'] * qty / 100, 1),
        round(food['fat']     * qty / 100, 1),
        round(food['carbs']   * qty / 100, 1),
    )


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if user:
        await update.message.reply_text(
            f"Hola *{user['name']}* 🥗\n\n"
            "*Cómo registrar:*\n"
            "• `5 huevos` — lo convierte solo a gramos\n"
            "• `almuerzo: 1 taza de arroz`\n"
            "• `cena 200g salmón`\n"
            "• Mandá una 📸 *foto de etiqueta* para guardarla\n\n"
            "*Comandos:*\n"
            "• /dia — resumen de hoy\n"
            "• /ayer — resumen de ayer\n"
            "• /semana — totales de la semana",
            parse_mode='Markdown'
        )
    else:
        keyboard = [[
            InlineKeyboardButton("⚡ Leo",  callback_data="fname_Leo"),
            InlineKeyboardButton("💚 Caro", callback_data="fname_Caro"),
        ]]
        await update.message.reply_text(
            "¡Hola! Soy tu bot de nutrición 🥗\n\n¿Quién sos?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def set_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    name = query.data.replace('fname_', '')
    db.create_user(query.from_user.id, name)
    await query.edit_message_text(
        f"✅ Listo, *{name}*!\n\n"
        "Mandame lo que comiste, por ejemplo:\n"
        "• `5 huevos`\n"
        "• `almuerzo: 1 taza de avena`\n"
        "• `cena 300g salmón`\n"
        "• Una 📸 foto de etiqueta nutricional",
        parse_mode='Markdown'
    )


# ── Handler de texto ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start para registrarte.")
        return

    text = update.message.text.strip()

    # Interceptar renombre de etiqueta
    if context.user_data.get('awaiting_label_rename'):
        context.user_data['awaiting_label_rename'] = False
        pending = context.user_data.get('pending_label')
        if pending:
            pending['food_name'] = text
            keyboard = [[
                InlineKeyboardButton("✅ Guardar en biblioteca", callback_data="label_save"),
                InlineKeyboardButton("❌ Cancelar",               callback_data="label_cancel"),
            ]]
            await update.message.reply_text(
                f"📋 Listo, guardar como:\n\n"
                f"*{text}* (por 100g)\n"
                f"{macros_line(pending['kcal'], pending['protein'], pending['fat'], pending['carbs'])}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("Expiró. Volvé a mandar la foto.")
        return

    thinking = await update.message.reply_text("⏳ Procesando...")

    # 1. Claude entiende el intent
    parsed = await understand_intent(text)
    if not parsed or parsed.get('intent') == 'unknown' or not parsed.get('food_name'):
        await thinking.edit_text(
            "No entendí 🤔\n\n"
            "Podés decirme:\n"
            "• Qué comiste: `5 huevos` o `almuerzo: 1 taza de arroz`\n"
            "• Agregar a biblioteca: `agrega dulce de leche`",
            parse_mode='Markdown'
        )
        return

    intent    = parsed.get('intent', 'log_food')
    food_name = parsed['food_name'].strip()

    # ── Intent: agregar a biblioteca ─────────────────────────────────────────
    if intent == 'add_to_library':
        kcal    = round(float(parsed.get('kcal',    0)), 1)
        protein = round(float(parsed.get('protein', 0)), 1)
        fat     = round(float(parsed.get('fat',     0)), 1)
        carbs   = round(float(parsed.get('carbs',   0)), 1)

        # ¿Ya existe en la biblioteca? (match estricto, no por palabras sueltas)
        existing = db.get_food_exact(food_name)
        if existing:
            await thinking.edit_text(
                f"📚 *{existing['name']}* ya está en tu biblioteca.\n"
                f"{macros_line(existing['kcal'], existing['protein'], existing['fat'], existing['carbs'])}",
                parse_mode='Markdown'
            )
            return

        context.user_data['pending_library_add'] = {
            'name': food_name, 'kcal': kcal, 'protein': protein,
            'fat': fat, 'carbs': carbs,
        }
        keyboard = [[
            InlineKeyboardButton("✅ Guardar en biblioteca", callback_data="library_add_confirm"),
            InlineKeyboardButton("❌ Cancelar",               callback_data="library_add_cancel"),
        ]]
        await thinking.edit_text(
            f"📚 ¿Guardar en biblioteca?\n\n"
            f"*{food_name}* (por 100g)\n"
            f"{macros_line(kcal, protein, fat, carbs)}\n\n"
            "_Valores estimados por Claude. Podés editarlos después desde la web._",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ── Intent: registrar comida (uno o varios) ───────────────────────────────
    items = parsed.get('items') or []
    # Fallback para modelos que devuelvan el formato viejo
    if not items and parsed.get('food_name') and parsed.get('quantity_g'):
        items = [{'food_name': parsed['food_name'],
                  'quantity_g': parsed['quantity_g'],
                  'meal_type': parsed.get('meal_type', 'general')}]

    if not items:
        await thinking.edit_text(
            f"No entendí la cantidad.\nProbá: `200g de pollo` o listá todo junto:\n`200g merluza\n100g arroz\n1 banana`",
            parse_mode='Markdown'
        )
        return

    today_ar  = datetime.now(AR).strftime('%Y-%m-%d')
    logged    = []   # {name, qty, kcal, meal_type}
    not_found = []   # {name, qty} — no estaban en ninguna DB

    # Si hay más de 1 ítem, mostrar mensaje de búsqueda
    if len(items) > 1:
        await thinking.edit_text(f"🔍 Buscando {len(items)} alimentos...")

    for item in items:
        food_name = (item.get('food_name') or '').strip()
        qty       = float(item.get('quantity_g') or 0)
        meal_type = item.get('meal_type') or 'general'
        if not food_name or qty <= 0:
            continue

        # Buscar en biblioteca local
        food = db.get_food_by_name(food_name)
        if food:
            kcal, protein, fat, carbs = calc_macros(food, qty)
            db.log_food_with_date(user_id, food['name'], qty, kcal, protein, fat, carbs, meal_type, today_ar)
            logged.append({'name': food['name'], 'qty': qty, 'kcal': kcal,
                           'protein': protein, 'fat': fat, 'carbs': carbs, 'meal_type': meal_type})
            continue

        # Buscar en Open Food Facts
        off = await search_off(food_name)
        if off:
            kcal, protein, fat, carbs = calc_macros(off, qty)
            db.log_food_with_date(user_id, off['name'], qty, kcal, protein, fat, carbs, meal_type, today_ar)
            logged.append({'name': off['name'], 'qty': qty, 'kcal': kcal,
                           'protein': protein, 'fat': fat, 'carbs': carbs, 'meal_type': meal_type})
        else:
            not_found.append({'name': food_name, 'qty': qty})

    # ── Respuesta ─────────────────────────────────────────────────────────────
    if not logged and not not_found:
        await thinking.edit_text("No pude procesar ningún alimento. Revisá el formato.")
        return

    # Caso simple: 1 ítem logueado, ninguno pendiente → mostrar confirmación con botón guardar
    if len(logged) == 1 and not not_found and len(items) == 1:
        l = logged[0]
        emoji = MEAL_EMOJIS.get(l['meal_type'], '🍽')
        await thinking.edit_text(
            f"{emoji} *{l['name']}* — {l['qty']:.0f}g\n"
            f"{macros_line(l['kcal'], l['protein'], l['fat'], l['carbs'])}",
            parse_mode='Markdown'
        )
        return

    # Caso múltiple: mostrar resumen
    lines = []
    total_kcal = sum(l['kcal'] for l in logged)
    total_prot = sum(l['protein'] for l in logged)

    for l in logged:
        emoji = MEAL_EMOJIS.get(l['meal_type'], '🍽')
        lines.append(f"{emoji} *{l['name']}* {l['qty']:.0f}g — {l['kcal']:.0f} kcal")

    if not_found:
        lines.append("")
        lines.append("❓ *No encontré:*")
        for n in not_found:
            lines.append(f"  • {n['name']} — usá `agrega {n['name']}` para agregarlo")

    if len(logged) > 1:
        lines.append(f"\n📊 *Total: {total_kcal:.0f} kcal | {total_prot:.1f}g prot*")

    await thinking.edit_text('\n'.join(lines), parse_mode='Markdown')


# ── Handler de macros manuales ────────────────────────────────────────────────

async def handle_manual_macros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        return
    text = update.message.text.strip()
    m = re.match(
        r'^(.+?)\s+(\d+(?:[.,]\d+)?)\s*g?\s+'
        r'(\d+(?:[.,]\d+)?)\s*kcal\s+'
        r'(\d+(?:[.,]\d+)?)\s*p\s+'
        r'(\d+(?:[.,]\d+)?)\s*g\s+'
        r'(\d+(?:[.,]\d+)?)\s*c$',
        text, re.IGNORECASE
    )
    if not m:
        return

    food_name = m.group(1).strip()
    qty     = float(m.group(2).replace(',', '.'))
    kcal    = float(m.group(3).replace(',', '.'))
    protein = float(m.group(4).replace(',', '.'))
    fat     = float(m.group(5).replace(',', '.'))
    carbs   = float(m.group(6).replace(',', '.'))

    db.log_food(user_id, food_name, qty, kcal, protein, fat, carbs, 'general')
    await update.message.reply_text(
        f"🍽 *{food_name}* — {qty:.0f}g\n{macros_line(kcal, protein, fat, carbs)}\n_(manual)_",
        parse_mode='Markdown'
    )


# ── Handler de fotos ──────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return

    thinking = await update.message.reply_text("📸 Leyendo etiqueta nutricional...")

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = bytes(await photo_file.download_as_bytearray())

    data = await read_label_with_claude(photo_bytes)

    if not data or not data.get('food_name'):
        await thinking.edit_text(
            "No pude leer la etiqueta. Asegurate de que sea clara, con buena luz y sin reflejos."
        )
        return

    # Si el usuario mandó la foto con un caption, usarlo como nombre
    caption = (update.message.caption or '').strip()
    if caption:
        data['food_name'] = caption

    context.user_data['pending_label'] = data
    keyboard = [[
        InlineKeyboardButton("✅ Guardar en biblioteca", callback_data="label_save"),
        InlineKeyboardButton("✏ Cambiar nombre",         callback_data="label_rename"),
        InlineKeyboardButton("❌ Cancelar",               callback_data="label_cancel"),
    ]]
    await thinking.edit_text(
        f"📋 Encontré:\n\n"
        f"*{data['food_name']}* (por 100g)\n"
        f"🔥 {data['kcal']} kcal  |  🥩 {data['protein']}g prot  |  🫒 {data['fat']}g grasas  |  🍚 {data['carbs']}g carbos\n\n"
        "¿Guardamos en la biblioteca?\n"
        "_Tip: podés mandar la foto con el nombre como texto (caption) para nombrarlo directo._",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

async def food_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ('food_save', 'food_nosave'):
        pending = context.user_data.pop('pending_food', None)
        if not pending:
            await query.edit_message_text("Expiró. Volvé a mandar el alimento.")
            return
        if data == 'food_save':
            db.add_food(pending['food_name'], pending['kcal_100'], pending['protein_100'],
                        pending['fat_100'], pending['carbs_100'])
        db.log_food(pending['user_id'], pending['food_name'], pending['quantity_g'],
                    pending['kcal'], pending['protein'], pending['fat'], pending['carbs'],
                    pending['meal_type'])
        emoji = MEAL_EMOJIS.get(pending['meal_type'], '🍽')
        saved_txt = " y guardado en la biblioteca 📚" if data == 'food_save' else ""
        await query.edit_message_text(
            f"✅ *{pending['food_name']}* registrado{saved_txt}\n"
            f"{emoji} {pending['quantity_g']:.0f}g — "
            f"{macros_line(pending['kcal'], pending['protein'], pending['fat'], pending['carbs'])}",
            parse_mode='Markdown'
        )

    elif data == 'food_cancel':
        context.user_data.pop('pending_food', None)
        await query.edit_message_text("❌ Cancelado.")

    elif data == 'label_save':
        pending = context.user_data.pop('pending_label', None)
        if not pending:
            await query.edit_message_text("Expiró. Volvé a mandar la foto.")
            return
        db.add_food(pending['food_name'], pending['kcal'], pending['protein'],
                    pending['fat'], pending['carbs'])
        await query.edit_message_text(
            f"✅ *{pending['food_name']}* guardado en la biblioteca 📚",
            parse_mode='Markdown'
        )

    elif data == 'label_rename':
        if 'pending_label' not in context.user_data:
            await query.edit_message_text("Expiró. Volvé a mandar la foto.")
            return
        context.user_data['awaiting_label_rename'] = True
        await query.edit_message_text(
            "✏ Mandame el nombre con el que querés guardar el alimento:"
        )

    elif data == 'label_cancel':
        context.user_data.pop('pending_label', None)
        context.user_data.pop('awaiting_label_rename', None)
        await query.edit_message_text("❌ Cancelado.")

    elif data == 'library_add_confirm':
        pending = context.user_data.pop('pending_library_add', None)
        if not pending:
            await query.edit_message_text("Expiró. Volvé a intentarlo.")
            return
        db.add_food(pending['name'], pending['kcal'], pending['protein'],
                    pending['fat'], pending['carbs'])
        await query.edit_message_text(
            f"✅ *{pending['name']}* guardado en la biblioteca 📚\n"
            f"{macros_line(pending['kcal'], pending['protein'], pending['fat'], pending['carbs'])}",
            parse_mode='Markdown'
        )

    elif data == 'library_add_cancel':
        context.user_data.pop('pending_library_add', None)
        await query.edit_message_text("❌ Cancelado.")

    elif data == 'delete_log_confirm':
        log_id = context.user_data.pop('pending_delete_log', None)
        if not log_id:
            await query.edit_message_text("Expiró.")
            return
        db.delete_food_log(log_id)
        await query.edit_message_text("✅ Registro eliminado.")

    elif data == 'delete_log_cancel':
        context.user_data.pop('pending_delete_log', None)
        await query.edit_message_text("❌ Cancelado.")


# ── /dia, /ayer, /semana ──────────────────────────────────────────────────────

async def dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _daily_summary(update, datetime.now(AR).strftime('%Y-%m-%d'), 'hoy')

async def ayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _daily_summary(update, (datetime.now(AR)-timedelta(days=1)).strftime('%Y-%m-%d'), 'ayer')

async def _daily_summary(update: Update, date: str, label: str):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return
    logs = db.get_food_logs_by_date(user_id, date)
    if not logs:
        await update.message.reply_text(f"No registraste comidas {label}.")
        return

    by_meal: dict = {}
    for log in logs:
        by_meal.setdefault(log['meal_type'], []).append(log)

    t_kcal = sum(l['kcal'] for l in logs)
    t_prot = sum(l['protein'] for l in logs)
    t_fat  = sum(l['fat']  for l in logs)
    t_carb = sum(l['carbs'] for l in logs)

    lines = [f"🍽 *Resumen de {label} — {user['name']}*\n"]
    for meal_type, items in by_meal.items():
        lines.append(f"{MEAL_EMOJIS.get(meal_type,'🍽')} *{meal_type.capitalize()}*")
        for item in items:
            lines.append(f"  • {item['food_name']} {item['quantity_g']:.0f}g — {item['kcal']:.0f} kcal")
        lines.append("")
    lines += [
        "📊 *Totales del día*",
        f"🔥 {t_kcal:.0f} kcal",
        f"🥩 Proteínas: {t_prot:.1f}g",
        f"🫒 Grasas: {t_fat:.1f}g",
        f"🍚 Carbos: {t_carb:.1f}g",
    ]
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return
    last = db.get_last_food_log(user_id)
    if not last:
        await update.message.reply_text("No tenés registros para borrar.")
        return
    context.user_data['pending_delete_log'] = last['id']
    keyboard = [[
        InlineKeyboardButton("✅ Sí, borrar", callback_data="delete_log_confirm"),
        InlineKeyboardButton("❌ No",          callback_data="delete_log_cancel"),
    ]]
    await update.message.reply_text(
        f"¿Borrar el último registro?\n\n"
        f"*{last['food_name']}* — {float(last['quantity_g']):.0f}g ({float(last['kcal']):.0f} kcal)",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return
    today = datetime.now(AR).date()
    lines = [f"📅 *Semana — {user['name']}*\n"]
    total = 0
    dias = 0
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        logs = db.get_food_logs_by_date(user_id, day.strftime('%Y-%m-%d'))
        if logs:
            kcal = sum(l['kcal'] for l in logs)
            prot = sum(l['protein'] for l in logs)
            total += kcal
            dias += 1
            label = 'Hoy' if i == 0 else day.strftime('%d/%m')
            lines.append(f"*{label}* — {kcal:.0f} kcal | P: {prot:.0f}g")
    if not dias:
        await update.message.reply_text("Sin registros esta semana.")
        return
    lines.append(f"\n🔥 *Promedio diario: {total/dias:.0f} kcal*")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()
    app = Application.builder().token(FOOD_TOKEN).build()

    app.add_handler(CommandHandler('start',  start))
    app.add_handler(CommandHandler('dia',    dia))
    app.add_handler(CommandHandler('ayer',   ayer))
    app.add_handler(CommandHandler('semana', semana))
    app.add_handler(CommandHandler('borrar', borrar))

    app.add_handler(CallbackQueryHandler(set_name_callback, pattern='^fname_'))
    app.add_handler(CallbackQueryHandler(food_callback,     pattern='^(food_|label_|library_|delete_log_)'))

    # Fotos → leer etiqueta
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Macros manuales (contiene "kcal")
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'\d+\s*kcal'),
        handle_manual_macros
    ))

    # Texto general → Claude
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot de comidas con IA iniciado. Ctrl+C para detener.")
    app.run_polling()


if __name__ == '__main__':
    main()
