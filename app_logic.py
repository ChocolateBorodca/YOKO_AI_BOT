import os
import sqlite3
import logging
import requests
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
        return row, row
    return 0, "default"

def set_user_mode(user_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, mode) VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
    ''', (int(user_id), mode))
    conn.commit()
    conn.close()

def activate_premium(user_id):
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
        # СТАБИЛЬНЫЙ РАБОЧИЙ ШЛЮЗ БЕЗ КЛЮЧЕЙ И БЕЗ БЛОКИРОВОК
        # Отправляем структурированный запрос через открытый эндпоинт
        url = "https://pollinations.ai"
        payload = {
            "messages": [
                {"role": "user", "content": f"{prompt}\n\nОтветь на сообщение пользователя: {user_text}"}
            ],
            "model": "searchgpt",
            "code": "true"
        }
        
        # Передаем обычные заголовки браузера, чтобы пройти проверки
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            answer = response.text.strip()
        else:
            answer = f"🔴 Ошибка сетевого узла ИИ (Код {response.status_code})"
            
    except Exception as e:
        answer = f"🔴 Сбой линии связи: {str(e)[:40]}"

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
