import os
import sqlite3
import logging
import requests
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

from utils import translate_to_burmalda, process_voice_message

YOUR_TELEGRAM_ID = 1151550758

try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: ADMIN_ID = 0

def init_db():
    pass

def get_user_data(user_id):
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
    # Промпт под хайповый режим Меллстроя
    prompt = "Ты — Меллстрой, хайповый стример. Говори дерзко, используй сленг: боров, легенда, хайп, суета, крутим слоты. Отвечай кратко, в 1-2 предложениях."

    try:
        # ЖЕЛЕЗОБЕТОННЫЙ URL-ШЛЮЗ: ИСПОЛЬЗУЕМ КРИСТАЛЬНО ЧИСТЫЙ GET-ЗАПРОС В ОБХОД КЛЮЧЕЙ И ЛИМИТОВ
        clean_text = requests.utils.quote(user_text)
        clean_prompt = requests.utils.quote(prompt)
        
        API_URL = f"https://pollinations.ai{clean_text}?system={clean_prompt}&model=searchgpt"
        
        response = requests.get(API_URL, timeout=12)
        
        if response.status_code == 200:
            answer = response.text.strip()
        else:
            answer = f"🔴 Ошибка сетевого узла ИИ (Код {response.status_code})"

    except Exception as e:
        answer = f"🔴 Сбой линии связи: {str(e)[:25]}"

    if not answer:
        answer = "ИИ-сервер обрабатывает поток данных, повтори запрос!"

    # В режиме /chat по умолчанию у нас всегда включена сочная Бурмалда
    if "🔴" not in answer: 
        answer = translate_to_burmalda(answer)
    return answer

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    await update.message.reply_text(await handle_ai_logic(user_id, user_text, "mellstroy"))

async def handle_voice_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_voice_message(update, context, os.getenv("HF_TOKEN"), handle_ai_logic, get_user_data)
