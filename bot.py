import logging
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv

import database as db
from exercises import WORKOUTS

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Estado de sesiones activas por usuario
# { user_id: { day_type, session_id, exercises, current_idx, logged } }
active_sessions: dict = {}

# Usuarios esperando elegir nombre al hacer /start
pending_name: set = set()


# ── Helpers ──────────────────────────────────────────────────────────────────

def main_menu_text(name: str) -> str:
    return (
        f"Hola *{name}* 💪 ¿Qué entrenás hoy?\n\n"
        "• /push — Día 1: Pecho · Hombro · Tríceps\n"
        "• /pull — Día 2: Espalda · Bíceps\n"
        "• /legs — Día 3: Piernas · Core\n"
        "• /historial — Últimas sesiones\n"
        "• /prs — Tus records personales"
    )


def format_weights(weights: list) -> str:
    return '  |  '.join(str(w) for w in weights)


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user:
        await update.message.reply_text(main_menu_text(user['name']), parse_mode='Markdown')
        return

    pending_name.add(user_id)
    keyboard = [[
        InlineKeyboardButton("⚡ Leo", callback_data="name_Leo"),
        InlineKeyboardButton("💚 Caro", callback_data="name_Caro"),
    ]]
    await update.message.reply_text(
        "¡Hola! Soy tu bot de gym 🏋️\n\nPrimero, ¿quién sos?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    name = query.data.replace('name_', '')
    db.create_user(user_id, name)
    pending_name.discard(user_id)
    await query.edit_message_text(
        f"✅ Listo, *{name}*!\n\n" + main_menu_text(name),
        parse_mode='Markdown'
    )


# ── Iniciar entrenamiento ─────────────────────────────────────────────────────

async def start_workout(update: Update, context: ContextTypes.DEFAULT_TYPE, day_type: str):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("Primero hacé /start para registrarte.")
        return

    if user_id in active_sessions:
        keyboard = [[
            InlineKeyboardButton("🔄 Sí, nueva sesión", callback_data=f"new_session_{day_type}"),
            InlineKeyboardButton("❌ No, seguir", callback_data="keep_session"),
        ]]
        await update.message.reply_text(
            "Ya tenés una sesión en curso. ¿Querés descartarla y empezar una nueva?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await _begin_workout(update, user_id, user['name'], day_type)


async def new_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    day_type = query.data.replace('new_session_', '')
    active_sessions.pop(user_id, None)
    user = db.get_user(user_id)
    await query.message.reply_text("Sesión anterior descartada.")
    await _begin_workout(query, user_id, user['name'], day_type)


async def keep_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Ok, seguís con la sesión anterior.")


async def _begin_workout(source, user_id: int, name: str, day_type: str):
    workout = WORKOUTS[day_type]
    session_id = db.create_session(user_id, day_type)

    active_sessions[user_id] = {
        'day_type': day_type,
        'session_id': session_id,
        'exercises': workout['exercises'],
        'current_idx': 0,
        'logged': {},
    }

    text = (
        f"{workout['emoji']} *{workout['title']}*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')} — {name}\n\n"
        "Te voy preguntando ejercicio por ejercicio.\n"
        "Mandá los pesos por serie separados por espacios: `80 82.5 80 80`\n"
        "Para Dominadas sin lastre podés mandar: `PC PC PC PC`\n\n"
        "• /saltar — saltear ejercicio\n"
        "• /cancelar — abandonar sesión"
    )

    if hasattr(source, 'message') and source.message:
        await source.message.reply_text(text, parse_mode='Markdown')
    else:
        await source.reply_text(text, parse_mode='Markdown')

    await _ask_exercise(source, user_id)


async def _ask_exercise(source, user_id: int):
    session = active_sessions.get(user_id)
    if not session:
        return

    idx = session['current_idx']
    exercises = session['exercises']

    if idx >= len(exercises):
        await _finish_session(source, user_id)
        return

    ex = exercises[idx]
    total = len(exercises)

    # Última vez que hizo este ejercicio
    last_session = db.get_last_session(user_id, session['day_type'])
    last_text = ''
    if last_session:
        for prev in last_session['exercises']:
            if prev['name'] == ex['name']:
                last_text = f"\n📅 Última vez: `{format_weights(prev['weights'])}`"
                break

    note_text = f"\n💡 _{ex['note']}_" if ex.get('note') else ''

    text = (
        f"*{idx + 1}/{total} — {ex['name']}*\n"
        f"📋 {ex['sets']} series × {ex['reps']} reps"
        f"{note_text}"
        f"{last_text}\n\n"
        "Pesos por serie:"
    )

    keyboard = [[InlineKeyboardButton("⏭ Saltar este ejercicio", callback_data="skip_ex")]]

    msg = source.message if hasattr(source, 'message') and source.message else source
    await msg.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


# ── Comandos del workout ──────────────────────────────────────────────────────

async def push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_workout(update, context, 'push')

async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_workout(update, context, 'pull')

async def legs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_workout(update, context, 'legs')


async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in active_sessions:
        await update.message.reply_text("No tenés ninguna sesión activa.")
        return
    session = active_sessions[user_id]
    ex = session['exercises'][session['current_idx']]
    await update.message.reply_text(f"⏭ Salteado: _{ex['name']}_", parse_mode='Markdown')
    session['current_idx'] += 1
    await _ask_exercise(update, user_id)


async def skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in active_sessions:
        return
    session = active_sessions[user_id]
    ex = session['exercises'][session['current_idx']]
    await query.message.reply_text(f"⏭ Salteado: _{ex['name']}_", parse_mode='Markdown')
    session['current_idx'] += 1
    await _ask_exercise(query, user_id)


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in active_sessions:
        active_sessions.pop(user_id)
        await update.message.reply_text("❌ Sesión cancelada.")
    else:
        await update.message.reply_text("No tenés ninguna sesión activa.")


# ── Recibir pesos ─────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in active_sessions:
        user = db.get_user(user_id)
        if user:
            await update.message.reply_text(
                "No hay sesión activa. Usá /push, /pull o /legs para empezar.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("Hacé /start para registrarte primero.")
        return

    session = active_sessions[user_id]
    idx = session['current_idx']
    ex = session['exercises'][idx]
    raw = update.message.text.strip()

    # Parsear pesos: soporta espacios, comas como decimal, "/" como separador
    parts = raw.replace('/', ' ').split()
    weights = []
    for p in parts:
        p = p.replace(',', '.')
        try:
            weights.append(float(p) if '.' in p else int(p))
        except ValueError:
            weights.append(p.upper())  # ej: "PC" para peso corporal

    if not weights:
        await update.message.reply_text(
            "No entendí eso. Mandá los pesos así: `80 82.5 80 80`",
            parse_mode='Markdown'
        )
        return

    # Detectar PR
    numeric = [w for w in weights if isinstance(w, (int, float))]
    pr_text = ''
    if numeric:
        max_today = max(numeric)
        prev_pr = db.get_pr(user_id, ex['name'])
        if prev_pr is None or max_today > prev_pr:
            pr_text = f"\n🏆 *¡NUEVO PR! {max_today} kg*"

    db.log_exercise(session['session_id'], ex['name'], weights)
    session['logged'][ex['name']] = weights

    await update.message.reply_text(
        f"✅ *{ex['name']}*\n`{format_weights(weights)}`{pr_text}",
        parse_mode='Markdown'
    )

    session['current_idx'] += 1
    await _ask_exercise(update, user_id)


# ── Terminar sesión ───────────────────────────────────────────────────────────

async def _finish_session(source, user_id: int):
    session = active_sessions.pop(user_id, {})
    logged = session.get('logged', {})
    day_type = session.get('day_type', '')

    workout_name = WORKOUTS[day_type]['title']
    lines = [f"🎉 *Sesión completada — {workout_name}*\n"]

    if logged:
        for ex_name, weights in logged.items():
            lines.append(f"• {ex_name}: `{format_weights(weights)}`")
    else:
        lines.append("_Sin ejercicios registrados._")

    msg = source.message if hasattr(source, 'message') and source.message else source
    await msg.reply_text('\n'.join(lines), parse_mode='Markdown')


# ── /historial ────────────────────────────────────────────────────────────────

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return

    args = context.args
    if args and args[0].lower() in WORKOUTS:
        await _send_historial(update.message, user_id, args[0].lower())
    else:
        keyboard = [[
            InlineKeyboardButton("Push", callback_data="hist_push"),
            InlineKeyboardButton("Pull", callback_data="hist_pull"),
            InlineKeyboardButton("Legs", callback_data="hist_legs"),
        ]]
        await update.message.reply_text(
            "¿Qué día querés ver?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def historial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day_type = query.data.replace('hist_', '')
    await _send_historial(query.message, query.from_user.id, day_type)


async def _send_historial(message, user_id: int, day_type: str):
    history = db.get_history(user_id, day_type, limit=3)
    workout_name = WORKOUTS[day_type]['title']

    if not history:
        await message.reply_text(f"Todavía no hay sesiones de {workout_name}.")
        return

    lines = [f"📊 *Historial — {workout_name}*\n"]
    for s in history:
        lines.append(f"📅 *{s['date']}*")
        for ex in s['exercises']:
            lines.append(f"  • {ex['name']}: `{format_weights(ex['weights'])}`")
        lines.append("")

    await message.reply_text('\n'.join(lines), parse_mode='Markdown')


# ── /prs ──────────────────────────────────────────────────────────────────────

async def prs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Primero hacé /start.")
        return

    all_prs = db.get_all_prs(user_id)
    if not all_prs:
        await update.message.reply_text("Todavía no tenés PRs registrados. ¡A entrenar! 💪")
        return

    lines = [f"🏆 *Records Personales — {user['name']}*\n"]
    for ex_name, weight in sorted(all_prs.items()):
        lines.append(f"• {ex_name}: *{weight} kg*")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db.init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('push', push))
    app.add_handler(CommandHandler('pull', pull))
    app.add_handler(CommandHandler('legs', legs))
    app.add_handler(CommandHandler('saltar', skip))
    app.add_handler(CommandHandler('cancelar', cancelar))
    app.add_handler(CommandHandler('historial', historial))
    app.add_handler(CommandHandler('prs', prs))

    app.add_handler(CallbackQueryHandler(set_name_callback, pattern='^name_'))
    app.add_handler(CallbackQueryHandler(skip_callback, pattern='^skip_ex$'))
    app.add_handler(CallbackQueryHandler(new_session_callback, pattern='^new_session_'))
    app.add_handler(CallbackQueryHandler(keep_session_callback, pattern='^keep_session$'))
    app.add_handler(CallbackQueryHandler(historial_callback, pattern='^hist_'))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot iniciado. Presioná Ctrl+C para detenerlo.")
    app.run_polling()


if __name__ == '__main__':
    main()
