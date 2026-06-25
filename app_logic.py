import os
import sqlite3
import logging
import requests
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

from utils import translate_to_burmalda, process_voice_message

OPENROUTER_API_KEY = os.getenv("HF_TOKEN")
YOUR_TELEGRAM_ID = 1151550758

try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: ADMIN_ID = 0

def init_db():
    # Заглушка для базы, чтобы убрать любые зависания процессов
    pass

def get_user_data(user_id):
    # Жесткая автономная проверка админа без запросов к битой базе данных
    if ADMIN_ID != 0 and int(user_id) == ADMIN_ID:
        return 1, "mellstroy"
    if int(user_id) == YOUR_TELEGRAM_ID:
        return 1, "mellstroy"
    return 0, "default"

def get_group_mode(chat_id):
    return "default"

def set_group_mode(chat_id, mode):
    pass

def set_user_mode(user_id, mode):
    pass

def save_message(user_id, role, content):
    pass

def get_chat_history(user_id, limit=6):
    # Возвращаем пустую историю, чтобы обойти поломку таблиц SQLite
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_info = (
         "🚀 **Привет я YOKO! Я универсальный ИИ-ассистент.**\n\n"
         "Вот список всех доступных команд проекта:\n"
         "😇 /yoko — Обычный вежливый ИИ (Бесплатно)\n"
         "⚡ /buy — Открыть расширенный Премиум доступ за 15 звезд\n"
         "🎰 /mellstroy — Вернуть режим Меллстроя (Если куплен)\n"
         "📋 /profile — Посмотреть свой ID и статус подписки"
    )
    await update.message.reply_text(start_info, parse_mode="Markdown")

async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("😇 Теперь с тобой общается обычный ИИ YOKO.")

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prices = [LabeledPrice("Премиум доступ YOKO AI", 15)]
        full_description = (
            "🔥 Премиум функции YOKO AI:\n"
            "• 🎙️ Безлимитный анализ голосовых сообщений (ГС).\n"
            "• 👥 Работа ассистента в группах и чатах для друзей.\n"
            "• 🧠 Расширенная память контекста диалога."
        )
        await context.bot.send_invoice(
            chat_id=update.message.chat_id, title="⚡ YOKO AI — Премиум функции",
            description=full_description[:250], payload="yoko_premium_payload",
            provider_token="", currency="XTR", prices=prices
        )
    except Exception as e: logging.error(f"Ошибка счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 МЕЛЛСТРОЙ ВЕРНУЛСЯ! Я снова общаюсь на языке Бурмалда. 🎰")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(f"📋 ТВОЙ ПРОФИЛЬ:\n• ID: {user_id}\n• Премиум: Активирован (Premium)")

async def handle_ai_logic(user_id, user_text, current_mode):
    if current_mode == "mellstroy":
        prompt = "Ты — Меллстрой, хайповый стример. Говори дерзко, используй сленг: боров, легенда, хайп, суета, крутим слоты. Отвечай кратко, в 1-2 предложения."
    else:
        prompt = "Ты — умный и вежливый ИИ-помощник YOKO. Отвечай кратко, грамотно, без сленга и мата."

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_text}
    ]

    try:
        API_URL = "https://openrouter.ai"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://render.com",
            "X-Title": "YokoBot"
        }
        payload = {
            "model": "ibm/granite-3.1-8b-instruct:free",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        answer = ""
        
        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json and len(res_json["choices"]) > 0:
                answer = res_json["choices"]["message"]["content"].strip()
        else:
            answer = f"🔴 Ошибка OpenRouter API (Статус-код: {response.status_code})"

    except Exception as e:
        answer = f"🔴 Ошибка соединения: {str(e)[:30]}"

    if not answer:
        answer = f"🔴 Не удалось получить ответ от модели IBM Granite."

    if current_mode == "mellstroy" and "🔴" not in answer: 
        answer = translate_to_burmalda(answer)
    return answer

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    # Передаем управление напрямую независимо от зависших таблиц БД
    await update.message.reply_text(await handle_ai_logic(user_id, user_text, "mellstroy"))

async def handle_voice_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_voice_message(update, context, os.getenv("HF_TOKEN"), handle_ai_logic, get_user_data)
