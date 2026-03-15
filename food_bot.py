import asyncio
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
    """
    Lee etiqueta en 2 pasos:
    1. Sonnet describe la tabla en JSON estructurado (por_porcion + por_100g separados)
    2. Python elige la mejor fuente y normaliza a /100g
    """
    img_b64   = base64.standard_b64encode(image_bytes).decode("utf-8")
    img_block = {"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg", "data": img_b64
    }}

    # ── PASO 1: descripción estructurada de la tabla ──────────────────────────
    try:
        r1 = await ai.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=900,
            messages=[{"role": "user", "content": [
                img_block,
                {"type": "text", "text":
                    """Analizá esta etiqueta nutricional argentina/latinoamericana.

PASO 1 — Formato:
  A) TABLA: columnas "Cantidad por Porción | 100g | %VD"
  B) PÁRRAFO/INLINE: texto corrido con ";" entre nutrientes

PASO 2 — Porción:
  Buscá "Porción X g" o "Tamaño de la porción: X g".
  Ese número es el portion_g. Ejemplo: "Porción 180 g (1 vaso)" → 180.

PASO 3 — Copiá textualmente (verbatim) los fragmentos que contienen cada nutriente:
  - "portion_text": toda la línea/frase que dice el tamaño de porción
  - "kcal_text": la parte que dice el valor energético. Ej: "Valor energético 137 kcal = 573 kJ"
  - "carbs_text": la parte con carbohidratos. Ej: "Carbohidratos 13 g (4% VD)"
  - "protein_text": la parte con proteínas. Ej: "Proteínas 9 g (12% VD)"
  - "fat_text": la parte que empieza con "Grasas totales" o "Lípidos totales".
    COPIÁ DESDE "Grasas totales" HASTA antes de "Grasas saturadas".
    Ej: "Grasas totales 5.4 g (10% VD)"  — NO incluyas lo que sigue después.
  - "fat_100g_text": si hay columna 100g, el valor de grasas totales en esa columna. Ej: "1 g"

PASO 4 — Columna /100g (solo TABLA):
  Si hay columna 100g: has_100g_col = true y completá por_100g con los valores numéricos.
  Si es PÁRRAFO: has_100g_col = false, por_100g todos -1.

Devolvé SOLO este JSON sin markdown:
{
  "name": "nombre o desconocido",
  "portion_text": "Porción 180 g (1 vaso)",
  "portion_g": 180,
  "has_100g_col": false,
  "kcal_text": "Valor energético 137 kcal = 573 kJ (7% VD)",
  "carbs_text": "Carbohidratos 13 g (4% VD)",
  "protein_text": "Proteínas 9 g (12% VD)",
  "fat_text": "Grasas totales 5.4 g (10% VD)",
  "fat_100g_text": "",
  "por_porcion": { "kcal": 137, "carbs": 13, "protein": 9, "fat": 5.4 },
  "por_100g":    { "kcal": -1,  "carbs": -1, "protein": -1, "fat": -1 }
}"""
                }
            ]}]
        )
        raw1 = r1.content[0].text.strip()
        raw1 = re.sub(r'```json?\n?', '', raw1).strip('`').strip()
        logging.info(f"[Label step1]\n{raw1}")
    except Exception as e:
        logging.error(f"Label step1 error: {e}")
        return None

    # ── PASO 2: normalización a /100g ─────────────────────────────────────────
    try:
        d        = json.loads(raw1)
        name     = d.get('name', 'desconocido')
        portion  = float(d.get('portion_g', 0) or 0)
        has_col  = bool(d.get('has_100g_col', False))
        pp       = d.get('por_porcion', {})
        p100     = d.get('por_100g', {})

        def safe(obj: dict, key: str) -> float:
            try:
                v = float(obj.get(key, -1) or -1)
                return v
            except (ValueError, TypeError):
                return -1.0

        def best(key: str) -> float:
            v100 = safe(p100, key)
            vp   = safe(pp,   key)
            # Preferir columna /100g si existe y es válida (>= 0)
            if has_col and v100 >= 0:
                return round(v100, 1)
            # Convertir desde porción
            if vp >= 0 and portion > 0:
                return round(vp * 100.0 / portion, 1)
            # Fallback: columna /100g aunque has_col sea False
            if v100 >= 0:
                return round(v100, 1)
            return 0.0

        kcal    = best('kcal')
        carbs   = best('carbs')
        protein = best('protein')
        fat     = best('fat')

        # ── Extracción de grasas por regex sobre texto verbatim ──────────────
        # Claude copia el texto crudo; Python extrae el número → evita confusión
        # con Grasas saturadas/trans/mono/poli
        def extract_fat_from_text(fat_text: str, fat_100g_text: str) -> float | None:
            # Si hay columna 100g, extraer de fat_100g_text
            for txt in [fat_100g_text, fat_text]:
                if not txt:
                    continue
                # Busca el PRIMER número decimal o entero en el texto
                m = re.search(r'(\d+[.,]\d+|\d+)\s*g?\b', txt)
                if m:
                    return float(m.group(1).replace(',', '.'))
            return None

        fat_text     = d.get('fat_text', '')
        fat_100g_txt = d.get('fat_100g_text', '')

        if has_col and fat_100g_txt:
            fat_from_text = extract_fat_from_text('', fat_100g_txt)
        else:
            fat_from_text = extract_fat_from_text(fat_text, '')

        if fat_from_text is not None and fat_from_text >= 0:
            # Convertir a /100g si es necesario
            if not has_col and portion > 0:
                fat_from_text = round(fat_from_text * 100.0 / portion, 1)
            logging.info(f"[fat_text] '{fat_text}' → fat={fat_from_text} (antes={fat})")
            fat = fat_from_text

        # ── Sanity 1: si kcal < carbs → Claude confundió filas completas ──────
        if kcal > 0 and carbs > 0 and kcal < carbs and portion > 0:
            logging.warning(f"[Label sanity1] kcal({kcal}) < carbs({carbs}), recalculando desde porción")
            kcal    = round(safe(pp, 'kcal')    * 100.0 / portion, 1) if safe(pp, 'kcal') >= 0 else kcal
            carbs   = round(safe(pp, 'carbs')   * 100.0 / portion, 1) if safe(pp, 'carbs') >= 0 else carbs
            protein = round(safe(pp, 'protein') * 100.0 / portion, 1) if safe(pp, 'protein') >= 0 else protein
            fat     = round(safe(pp, 'fat')     * 100.0 / portion, 1) if safe(pp, 'fat') >= 0 else fat

        # ── Sanity 2: fórmula calórica 4P + 4C + 9F ≈ kcal ─────────────────
        if kcal > 0 and protein >= 0 and carbs >= 0:
            calc_kcal = 4.0 * protein + 4.0 * carbs + 9.0 * fat
            if calc_kcal > 0 and (kcal / calc_kcal) > 1.15:
                fat_corr = round((kcal - 4.0 * protein - 4.0 * carbs) / 9.0, 1)
                if fat_corr > fat:
                    logging.warning(f"[Label sanity2] calc_kcal={calc_kcal:.1f} vs kcal={kcal:.1f} → fat {fat}→{fat_corr}")
                    fat = max(fat_corr, 0.0)

        return {
            "food_name":        name,
            "kcal":             max(kcal,    0.0),
            "protein":          max(protein, 0.0),
            "fat":              max(fat,     0.0),
            "carbs":            max(carbs,   0.0),
            "portion_g":        portion,
            "kcal_per_portion": max(safe(pp, 'kcal'), 0.0),
        }
    except Exception as e:
        logging.error(f"Label step2 error: {e}")
        return None


# ── Claude: estimar macros de un alimento desconocido ────────────────────────

async def estimate_macros_with_claude(food_name: str) -> dict | None:
    """
    Promedia múltiples fuentes online (USDA + OFF) para mayor precisión.
    Solo usa estimación de Claude como último recurso.
    """
    # 1. Buscar en USDA y OFF en paralelo
    usda_results, off_results = await asyncio.gather(
        search_usda_multi(food_name),
        search_off_multi(food_name),
    )

    all_results = usda_results + off_results
    if all_results:
        avg = _average_results(all_results)
        n_usda = len(usda_results)
        n_off  = len(off_results)
        source_tag = f"promedio {n_usda} USDA + {n_off} OFF" if n_off else f"promedio {n_usda} USDA"
        logging.info(f"[estimate] '{food_name}' → {source_tag}: {avg}")
        return {
            "name":      food_name,
            "source":    source_tag,
            "estimated": False,
            **avg,
        }

    # 2. Fallback: Claude como último recurso
    logging.warning(f"[estimate] Sin datos online para '{food_name}', usando Claude")
    try:
        resp = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content":
                f"""Sos un nutricionista experto. Estimá los macros por 100g de: "{food_name}"
Crudo ≠ cocido (pollo crudo ~20g prot, cocido ~31g). Frito tiene más grasa.
Devolvé SOLO JSON: {{"kcal":0,"protein":0,"fat":0,"carbs":0}}"""
            }]
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r'```json?\n?', '', raw).strip('`').strip()
        data = json.loads(raw)
        return {
            "name": food_name, "estimated": True,
            "kcal":    round(float(data.get("kcal",    0)), 1),
            "protein": round(float(data.get("protein", 0)), 1),
            "fat":     round(float(data.get("fat",     0)), 1),
            "carbs":   round(float(data.get("carbs",   0)), 1),
        }
    except Exception as e:
        logging.error(f"Claude estimate error: {e}")
    return None


# ── Open Food Facts ───────────────────────────────────────────────────────────

async def search_off(name: str) -> dict | None:
    """Promedia múltiples resultados relevantes de Open Food Facts."""
    results = await search_off_multi(name)
    if not results:
        return None
    avg = _average_results(results)
    return {"name": name, **avg}


# ── USDA FoodData Central ────────────────────────────────────────────────────

async def search_usda_multi(food_name_es: str) -> list[dict]:
    """Devuelve todos los resultados relevantes de USDA (hasta 8), para promediar."""
    try:
        tr = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f"Translate this Spanish food name to English for USDA nutrition database. "
                f"Be specific about preparation (raw, cooked, fried, etc.). "
                f"Return 1-3 keywords that MUST appear in matching results. "
                f"Food: '{food_name_es}'. "
                f"Reply ONLY JSON: {{\"query\":\"...\",\"keywords\":[\"...\"]}}"
            }]
        )
        raw = tr.content[0].text.strip()
        raw = re.sub(r'```json?\n?', '', raw).strip('`').strip()
        tr_data = json.loads(raw)
        english_name = tr_data.get("query", food_name_es)
        keywords = [k.lower() for k in tr_data.get("keywords", [])]
    except Exception as e:
        logging.error(f"[USDA] translation error: {e}")
        english_name = food_name_es
        keywords = []

    # Usar solo la keyword principal (sin prep words) para el query USDA.
    # "hake, cooked" confunde el ranking de relevancia → buscar solo "hake"
    PREP_WORDS = {"cooked","raw","fried","boiled","grilled","baked",
                  "roasted","steamed","dried","fresh","frozen","canned"}
    food_keywords = [k for k in keywords if k not in PREP_WORDS]
    main_keyword = food_keywords[0] if food_keywords else english_name.split(",")[0].split()[0]
    logging.info(f"[USDA] '{food_name_es}' → main_keyword='{main_keyword}' filter_words={food_keywords or [main_keyword]}")

    api_key = os.environ.get("USDA_API_KEY", "DEMO_KEY")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.nal.usda.gov/fdc/v1/foods/search",
                params={
                    "query": main_keyword,
                    "api_key": api_key,
                    "dataType": "Foundation,SR Legacy",
                    "pageSize": 20,
                }
            )
        foods = resp.json().get("foods", [])
    except Exception as e:
        logging.error(f"[USDA] request error: {e}")
        return []

    filter_words = food_keywords if food_keywords else [main_keyword]

    results = []
    for food in foods:
        desc = food.get("description", "").lower()
        # Rechazar si ninguna keyword específica del alimento aparece en la descripción
        if filter_words and not any(w in desc for w in filter_words):
            continue
        nutrients = {n["nutrientId"]: n["value"] for n in food.get("foodNutrients", [])}
        kcal = float(nutrients.get(1008, 0))
        if kcal <= 0:
            continue
        results.append({
            "source":  food.get("description", english_name),
            "kcal":    kcal,
            "protein": float(nutrients.get(1003, 0)),
            "fat":     float(nutrients.get(1004, 0)),
            "carbs":   float(nutrients.get(1005, 0)),
        })
        if len(results) >= 8:
            break

    logging.info(f"[USDA] '{english_name}' filter={filter_words} → {len(results)} resultados: {[r['source'][:35] for r in results]}")
    return results


async def _off_search_terms(terms: str, query_words: list[str]) -> list[dict]:
    """Busca en OFF con ciertos términos y filtra por relevancia."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": terms, "search_simple": 1,
                    "action": "process", "json": 1, "page_size": 20,
                    "fields": "product_name,nutriments",
                }
            )
        # Palabras de productos procesados/preparados — no sirven para ingredientes genéricos
        PROCESSED = {"rebozad","empan","frit","roman","gratin","preparad",
                     "precocid","plat","apanad","tempura","nugget","croqueta"}
        results = []
        for product in resp.json().get("products", []):
            n = product.get("nutriments", {})
            kcal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
            if not kcal or float(kcal) <= 0:
                continue
            pname = (product.get("product_name") or "").lower()
            # El término debe aparecer en el nombre
            if not any(w in pname for w in query_words):
                continue
            # Excluir productos procesados (rebozado, empanado, etc.)
            if any(p in pname for p in PROCESSED):
                continue
            # Excluir productos con nombre muy largo (platos preparados)
            # "Merluza" o "Filetes de merluza" OK; "Merluza al limón con salsa..." no
            if len(pname.split()) > 4:
                continue
            results.append({
                "source":  product.get("product_name", terms),
                "kcal":    float(kcal),
                "protein": float(n.get("proteins_100g",      0)),
                "fat":     float(n.get("fat_100g",           0)),
                "carbs":   float(n.get("carbohydrates_100g", 0)),
            })
            if len(results) >= 6:
                break
        logging.info(f"[OFF] '{terms}' → {len(results)} resultados tras filtro: {[r['source'][:30] for r in results]}")
        return results
    except Exception as e:
        logging.error(f"OFF search '{terms}' error: {e}")
        return []


async def search_off_multi(name: str) -> list[dict]:
    """
    Busca en OFF en español primero, luego en inglés si no hay resultados.
    Devuelve hasta 6 resultados relevantes para promediar.
    """
    query_words = [w for w in name.lower().split() if len(w) > 2]

    # Búsqueda en español
    results = await _off_search_terms(name, query_words)

    # Si no hay resultados, traducir al inglés y buscar de nuevo
    if not results:
        try:
            tr = await ai.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=30,
                messages=[{"role": "user", "content":
                    f"Translate to English (1-2 words only): '{name}'. Reply ONLY the translation."
                }]
            )
            en_name = tr.content[0].text.strip().lower()
            en_words = [w for w in en_name.split() if len(w) > 2]
            if en_name and en_name != name.lower():
                results = await _off_search_terms(en_name, en_words or query_words)
                logging.info(f"[OFF] '{name}' → '{en_name}' (EN) → {len(results)} resultados")
        except Exception:
            pass

    logging.info(f"[OFF] '{name}' total → {len(results)} resultados")
    return results


def _average_results(results: list[dict]) -> dict:
    """Promedia una lista de resultados nutricionales (outlier filtering incluido)."""
    if not results:
        return {}
    n = len(results)
    avg = {
        "kcal":    sum(r["kcal"]    for r in results) / n,
        "protein": sum(r["protein"] for r in results) / n,
        "fat":     sum(r["fat"]     for r in results) / n,
        "carbs":   sum(r["carbs"]   for r in results) / n,
    }
    # Filtrar outliers: descartar valores > 2× el promedio en kcal
    if n > 2:
        filtered = [r for r in results if abs(r["kcal"] - avg["kcal"]) < avg["kcal"] * 0.8]
        if len(filtered) >= 2:
            n2 = len(filtered)
            avg = {
                "kcal":    sum(r["kcal"]    for r in filtered) / n2,
                "protein": sum(r["protein"] for r in filtered) / n2,
                "fat":     sum(r["fat"]     for r in filtered) / n2,
                "carbs":   sum(r["carbs"]   for r in filtered) / n2,
            }
    return {k: round(v, 1) for k, v in avg.items()}


async def search_usda(food_name_es: str) -> dict | None:
    """Busca en USDA y promedia resultados relevantes."""
    results = await search_usda_multi(food_name_es)
    if not results:
        return None
    avg = _average_results(results)
    sources = ", ".join(r["source"][:25] for r in results[:3])
    return {"name": food_name_es, **avg, "source": sources}


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

    # Interceptar edición de macros de etiqueta
    if context.user_data.get('awaiting_label_macros'):
        context.user_data['awaiting_label_macros'] = False
        pending = context.user_data.get('pending_label')
        if pending:
            try:
                parts = text.replace(',', '.').split()
                vals = [float(p) for p in parts if re.match(r'^\d+(\.\d+)?$', p)]
                if len(vals) < 4:
                    raise ValueError
                pending['kcal']    = round(vals[0], 1)
                pending['protein'] = round(vals[1], 1)
                pending['fat']     = round(vals[2], 1)
                pending['carbs']   = round(vals[3], 1)
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Guardar",       callback_data="label_save"),
                        InlineKeyboardButton("✏ Editar macros",  callback_data="label_edit_macros"),
                    ],
                    [
                        InlineKeyboardButton("✏ Cambiar nombre", callback_data="label_rename"),
                        InlineKeyboardButton("❌ Cancelar",       callback_data="label_cancel"),
                    ],
                ]
                await update.message.reply_text(
                    f"📋 *{pending['food_name']}* (por 100g)\n\n"
                    f"🔥 {pending['kcal']} kcal\n"
                    f"🥩 {pending['protein']}g proteína\n"
                    f"🫒 {pending['fat']}g grasas\n"
                    f"🍚 {pending['carbs']}g carbos\n\n"
                    "¿Guardamos?",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except (ValueError, IndexError):
                context.user_data['awaiting_label_macros'] = True
                await update.message.reply_text(
                    "❌ Formato incorrecto. Mandá 4 números separados por espacios:\n"
                    "`kcal proteina grasa carbo`\n"
                    "Ejemplo: `143 27 4 0`",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("Expiró. Volvé a mandar la foto.")
        return

    # Interceptar renombre de etiqueta
    if context.user_data.get('awaiting_label_rename'):
        context.user_data['awaiting_label_rename'] = False
        pending = context.user_data.get('pending_label')
        if pending:
            pending['food_name'] = text
            keyboard = [
                [
                    InlineKeyboardButton("✅ Guardar",       callback_data="label_save"),
                    InlineKeyboardButton("✏ Editar macros",  callback_data="label_edit_macros"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar",       callback_data="label_cancel"),
                ],
            ]
            await update.message.reply_text(
                f"📋 *{text}* (por 100g)\n\n"
                f"🔥 {pending['kcal']} kcal\n"
                f"🥩 {pending['protein']}g proteína\n"
                f"🫒 {pending['fat']}g grasas\n"
                f"🍚 {pending['carbs']}g carbos\n\n"
                "¿Guardamos?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("Expiró. Volvé a mandar la foto.")
        return

    thinking = await update.message.reply_text("⏳ Procesando...")

    # 1. Claude entiende el intent
    parsed = await understand_intent(text)
    intent = parsed.get('intent', 'unknown') if parsed else 'unknown'

    if not parsed or intent == 'unknown':
        await thinking.edit_text(
            "No entendí 🤔\n\n"
            "Podés decirme:\n"
            "• Qué comiste: `5 huevos` o `almuerzo: 1 taza de arroz`\n"
            "• Agregar a biblioteca: `agrega dulce de leche`",
            parse_mode='Markdown'
        )
        return

    if intent == 'add_to_library' and not parsed.get('food_name'):
        await thinking.edit_text(
            "No entendí 🤔\n\n"
            "Podés decirme:\n"
            "• Qué comiste: `5 huevos` o `almuerzo: 1 taza de arroz`\n"
            "• Agregar a biblioteca: `agrega dulce de leche`",
            parse_mode='Markdown'
        )
        return

    food_name = parsed.get('food_name', '').strip()

    # ── Intent: agregar a biblioteca ─────────────────────────────────────────
    if intent == 'add_to_library':
        # ¿Ya existe en la biblioteca? (match estricto, no por palabras sueltas)
        existing = db.get_food_exact(food_name)
        if existing:
            await thinking.edit_text(
                f"📚 *{existing['name']}* ya está en tu biblioteca.\n"
                f"{macros_line(existing['kcal'], existing['protein'], existing['fat'], existing['carbs'])}",
                parse_mode='Markdown'
            )
            return

        await thinking.edit_text("🔍 Buscando en USDA, Open Food Facts y fuentes online...")

        # Buscar en todas las fuentes (USDA + OFF en paralelo) y promediar
        data = await estimate_macros_with_claude(food_name)
        if data and not data.get('estimated'):
            kcal, protein, fat, carbs = data['kcal'], data['protein'], data['fat'], data['carbs']
            src = data.get('source', '')
            source_note = f"_Fuente: {src}_" if src else "_Fuente: USDA / Open Food Facts_"
        else:
            # Último recurso: estimación de Claude
            kcal    = round(float(data['kcal']    if data else parsed.get('kcal',    0)), 1)
            protein = round(float(data['protein'] if data else parsed.get('protein', 0)), 1)
            fat     = round(float(data['fat']     if data else parsed.get('fat',     0)), 1)
            carbs   = round(float(data['carbs']   if data else parsed.get('carbs',   0)), 1)
            source_note = "_Valores estimados por IA. Podés editarlos después desde la web._"

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
            f"{source_note}",
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
            # Fallback: Claude estima macros
            est = await estimate_macros_with_claude(food_name)
            if est:
                kcal, protein, fat, carbs = calc_macros(est, qty)
                db.log_food_with_date(user_id, food_name, qty, kcal, protein, fat, carbs, meal_type, today_ar)
                logged.append({'name': food_name, 'qty': qty, 'kcal': kcal,
                               'protein': protein, 'fat': fat, 'carbs': carbs,
                               'meal_type': meal_type, 'estimated': True})
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
        est_note = "\n_~valores estimados por IA_" if l.get('estimated') else ""
        await thinking.edit_text(
            f"{emoji} *{l['name']}* — {l['qty']:.0f}g\n"
            f"{macros_line(l['kcal'], l['protein'], l['fat'], l['carbs'])}{est_note}",
            parse_mode='Markdown'
        )
        return

    # Caso múltiple: mostrar resumen
    lines = []
    total_kcal = sum(l['kcal'] for l in logged)
    total_prot = sum(l['protein'] for l in logged)

    for l in logged:
        emoji = MEAL_EMOJIS.get(l['meal_type'], '🍽')
        est_tag = " _(~estimado)_" if l.get('estimated') else ""
        lines.append(f"{emoji} *{l['name']}* {l['qty']:.0f}g — {l['kcal']:.0f} kcal{est_tag}")

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
    caption = (update.message.caption or '').strip()

    # Si Claude falló completamente pero hay caption → dejar entrar con macros en 0 para editar
    if not data and caption:
        data = {'food_name': caption, 'kcal': 0, 'protein': 0, 'fat': 0, 'carbs': 0,
                'portion_g': 0, 'kcal_per_portion': 0}

    # Aplicar caption como nombre (tiene prioridad sobre lo que Claude leyó)
    if data and caption:
        data['food_name'] = caption

    has_macros = bool(data and data.get('kcal', 0) > 0)
    has_name   = bool(data and data.get('food_name') and data.get('food_name') != 'desconocido')

    # Sin datos Y sin caption → error total
    if not data:
        await thinking.edit_text(
            "⚠️ No pude leer la etiqueta.\n\n"
            "• Intentá con mejor luz / menos ángulo\n"
            "• O ingresá los valores manualmente:\n"
            "`agrega <nombre> 342kcal 7prot 0grasas 78carbos`",
            parse_mode='Markdown'
        )
        return

    # Tenemos datos pero sin nombre → pedir caption
    if not has_name:
        await thinking.edit_text(
            "⚠️ Leí los macros pero no el nombre.\n"
            "Volvé a mandar la foto con el nombre como texto adjunto (caption).",
            parse_mode='Markdown'
        )
        return

    context.user_data['pending_label'] = data
    portion_g = data.get('portion_g', 0)
    kcal_pp   = data.get('kcal_per_portion', 0)
    source_note = (
        f"\n_Porción leída: {portion_g}g → convertido a /100g_"
        if portion_g and portion_g > 0 else
        "\n_Valores tomados directamente de columna /100g_"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Guardar",          callback_data="label_save"),
            InlineKeyboardButton("✏ Editar macros",     callback_data="label_edit_macros"),
        ],
        [
            InlineKeyboardButton("✏ Cambiar nombre",    callback_data="label_rename"),
            InlineKeyboardButton("❌ Cancelar",          callback_data="label_cancel"),
        ],
    ]
    await thinking.edit_text(
        f"📋 *{data['food_name']}* (por 100g)\n\n"
        f"🔥 {data['kcal']} kcal\n"
        f"🥩 {data['protein']}g proteína\n"
        f"🫒 {data['fat']}g grasas\n"
        f"🍚 {data['carbs']}g carbos"
        f"{source_note}\n\n"
        "¿Son correctos los valores?",
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

    elif data == 'label_edit_macros':
        if 'pending_label' not in context.user_data:
            await query.edit_message_text("Expiró. Volvé a mandar la foto.")
            return
        context.user_data['awaiting_label_macros'] = True
        p = context.user_data['pending_label']
        await query.edit_message_text(
            f"✏ *Editar macros de {p['food_name']}*\n\n"
            f"Valores actuales (por 100g):\n"
            f"  🔥 {p['kcal']} kcal  |  🥩 {p['protein']}g  |  🫒 {p['fat']}g  |  🍚 {p['carbs']}g\n\n"
            "Mandame los valores corregidos en este formato:\n"
            "`kcal proteina grasa carbo`\n\n"
            "Ejemplo: `143 27 4 0`",
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
        context.user_data.pop('awaiting_label_macros', None)
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
