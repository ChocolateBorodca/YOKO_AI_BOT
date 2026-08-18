import os
import sqlite3
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

from utils import translate_to_burmalda, process_voice_message

YOUR_TELEGRAM_ID = 1151550758
DB_FILE = "bot_database.db"

try: 
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: 
    ADMIN_ID = 0

def init_db():
    """Создает базу данных и таблицу пользователей при первом старте"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'default'
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    """Получает статус и режим пользователя из реальной базы данных"""
    if ADMIN_ID != 0 and int(user_id) == ADMIN_ID:
        return 1, "mellstroy"
    if int(user_id) == YOUR_TELEGRAM_ID:
        return 1, "mellstroy"
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium, mode FROM users WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row[0], row[1]
    return 0, "default"

def set_user_mode(user_id, mode):
    """Переключает текущий текстовый режим пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, mode) VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
    ''', (int(user_id), mode))
    conn.commit()
    conn.close()

def activate_premium(user_id):
    """Выдает пользователю вечный Премиум статус в базе данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, is_premium) VALUES(?, 1)
        ON CONFLICT(user_id) DO UPDATE SET is_premium=1
    ''', (int(user_id),))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_info = (
         "🚀 **Привет, я YOKO! Я твой продвинутый ИИ-ассистент.**\n\n"
         "Вот список всех доступных команд проекта:\n"
         "😇 /yoko — Обычный вежливый ИИ (Бесплатно)\n"
         "⚡ /buy — Открыть расширенный Премиум доступ за 15 звезд\n"
         "🎰 /mellstroy — Вернуть режим Меллстроя (Если куплен)\n"
         "📋 /profile — Посмотреть свой ID и статус подписки"
    )
    await update.message.reply_text(start_info, parse_mode="Markdown")

async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    set_user_mode(user_id, "default")
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
    except Exception as e: 
        logging.error(f"Ошибка выставления счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Срабатывает в момент реального перевода Telegram Stars"""
    user_id = update.message.from_user.id
    activate_premium(user_id)
    set_user_mode(user_id, "mellstroy")
    await update.message.reply_text("🎉 Спасибо за покупку! Премиум успешно активирован. Режим МЕЛЛСТРОЯ включен! 🎰")

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, _ = get_user_data(user_id)
    if not is_premium:
        await update.message.reply_text("❌ Режим Меллстроя доступен только после покупки премиума! Нажми /buy ⚡")
        return
    set_user_mode(user_id, "mellstroy")
    await update.message.reply_text("🔥 МЕЛЛСТРОЙ ВЕРНУЛСЯ! Я снова общаюсь на языке Бурмалда. 🎰")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, mode = get_user_data(user_id)
    status = "Активирован (Premium) 👑" if is_premium else "Базовый (Бесплатный) 😇"
    await update.message.reply_text(f"📋 ТВОЙ ПРОФИЛЬ:\n• ID: {user_id}\n• Статус: {status}\n• Активный режим: {mode}")

async def handle_ai_logic(user_id, user_text, current_mode):
    if current_mode == "mellstroy":
        prompt = "Ты — Меллстрой, хайповый стример. Говори дерзко, используй сленг: боров, легенда, хайп, суета, крутим слоты. Отвечай кратко, в 1-2 предложениях."
    else:
        prompt = "Ты — вежливый и полезный ИИ ассистент по имени YOKO. Отвечай дружелюбно, грамотно и коротко."

    try:
        # СТАБИЛЬНЫЙ ОФИЦИАЛЬНЫЙ ДВИЖОК DUCKDUCKGO
        from duckduckgo_search import DDGS
        
        full_message = f"Инструкция: {prompt}\nПользователь: {user_text}"
        
        with DDGS() as ddgs:
            # ЖЕЛЕЗОБЕТОННО ПОД ПОСЛЕДНЮЮ ВЕРСИЮ: Передаем через keywords=
            response = ddgs.text(keywords=full_message, model="gpt-4o-mini")
            
        if response:
            answer = response.strip()
        else:
            answer = "🔴 ИИ вернул пустой ответ, повтори запрос."
            
    except Exception as e:
        answer = f"🔴 Сбой линии ИИ: {str(e)[:40]}"

    if not answer:
        answer = "ИИ-сервер обрабатывает поток данных, повтори запрос!"

    if current_mode == "mellstroy" and "🔴" not in answer: 
        answer = translate_to_burmalda(answer)
    return answer

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    _, current_mode = get_user_data(user_id)
    
    await update.message.reply_text(await handle_ai_logic(user_id, user_text, current_mode))

async def handle_voice_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_voice_message(update, context, os.getenv("HF_TOKEN"), handle_ai_logic, get_user_data)
