import os
import threading
import logging
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, LabeledPrice, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from huggingface_hub import InferenceClient

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

client = InferenceClient("Qwen/Qwen2.5-Coder-7B-Instruct", token=HF_TOKEN)

DB_FILE = "yoko_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT is_premium FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute('INSERT INTO users (user_id, is_premium) VALUES (?, 0)', (user_id,))
        conn.commit()
        return 0
    conn.close()
    return row

def set_user_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET is_premium=1', (user_id,))
    conn.commit()
    conn.close()

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health():
    server = HTTPServer(('0.0.0.0', 10000), Health)
    server.serve_forever()

START_TEXT = """Привет я YOKO! Я ИИ бот бурмалда
Используй команду /buy чтобы открыть секретный режим!"""

DEFAULT_PROMPT = "Ты дружелюбный и вежливый ИИ-помощник YOKO. Отвечай кратко на русском языке."

MELLSTROY_PROMPT = """Ты — Меллстрой (Mellstroy), скандальный стример, но ты общаешься СТРОГО на выдуманном языке "Бурмалда".
Твой стиль: хайповый, дерзкий, угарный. Используй слова: "боров", "легенда", "бубс", "осуждаю", "крутим слоты", "че за суета", капс и эмодзи (🔥, 🎰, 💰, 👑).

ЖЕСТКИЕ ПРАВИЛА ЯЗЫКА БУРМАЛДА ДЛЯ ТЕБЯ (СОБЛЮДАЙ ВСЕГДА):
1. Слова-исключения:
   - Вместо местоимения "я" ты ВСЕГДА пишешь "ч" (например: "ч пришел", "ч даю тебе лям").
   - Вместо слово "дед" ты ВСЕГДА пишешь "дод".
   - Вместо слова "жена" ты ВСЕГДА пишешь "жинка".
2. Правило суффиксов:
   - КО ВСЕМ СУЩЕСТВИТЕЛЬНЫМ без исключения ты обязан добавлять окончание "ость" или "сть".
   - Примеры: дом -> домость, кот -> котость, хвост -> хвостость, стрим -> стримость, бабки -> бабкость, боров -> боровость, суета -> суетость, работа -> работость.
   - Пример правильного предложения: "ч пришел в домость и увидел котость у котости черный хвостость".

Отвечай эмоционально, угарно, сочетай стиль Меллстроя и правила языка Бурмалда! Отвечай кратко."""

# Установка списка команд для всех по умолчанию
async def set_default_commands(application):
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("buy", "⚡ Открыть режим МЕЛЛСТРОЯ (1 звезда)"),
        BotCommand("mellstroy", "🎰 Меню Меллстроя (Только для Премиум)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        prices = [LabeledPrice("Бурмалда Premium", 1)]
        await context.bot.send_invoice(
            chat_id=chat_id,
            title="🎰 МЕЛЛСТРОЙ НА БУРМАЛДЕ",
            description="Открывает Premium режим! Меллстрой начнет суетить в чате строго на языке Бурмалда.",
            payload="yoko_premium_payload",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        logging.error(f"Ошибка выставления счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    set_user_premium(user_id)
    await update.message.reply_text("🎰 ЕС ТУ ДЕЙ! Премиумность активирована! Ч в здании, пиши мне, боровость! Теперь команда /mellstroy разблокирована! 🔥")

# Команда /mellstroy с проверкой подписки
async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium = get_user_premium(user_id)
    
    if not is_premium:
        await update.message.reply_text("❌ Эй, боров! Эта команда заблокирована! Сначала активируй режим Меллстроя через /buy 🎰")
        return
        
    await update.message.reply_text(
        "🔥 ДОБРО ПОЖАЛОВАТЬ В БУРМАЛДУ, ЛЕГЕНДА!\n\n"
        "Ч теперь общаюсь с тобой только так. Напоминаю правила для правильных боровостей:\n"
        "1. Вместо 'я' пиши строго 'ч'\n"
        "2. Вместо 'дед' пиши 'дод', вместо 'жена' — 'жинка'\n"
        "3. Ко всем сущностям лепи суффиксость 'ость' / 'сть'!\n\n"
        "Задавай мне любой вопросирость, крутим слотость! 🎰💰"
    )

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    
    if update.message.chat.type in ['group', 'supergroup']:
        is_premium = get_user_premium(user_id)
        if not is_premium:
            await update.message.reply_text("❌ Эй, боровость! Чтобы ч суетил в вашей группости, у тебя должна быть Премиумность! До свиданьесть! 🎰")
            await context.bot.leave_chat(update.message.chat_id)
            return

    is_premium = get_user_premium(user_id)
    system_prompt = MELLSTROY_PROMPT if is_premium else DEFAULT_PROMPT
    
    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=500
        )
        if isinstance(response, dict):
            answer = response['choices']['message']['content']
        elif isinstance(response, list):
            answer = response['message']['content']
        else:
            answer = response.choices.message.content
            
        await update.message.reply_text(answer)
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        await update.message.reply_text("Я немного задумался, напиши чуть позже!")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium = get_user_premium(user_id)
    if not is_premium:
        await update.message.reply_text("❌ Записывать голосовость Меллстрою? Только для Premium боровостей! Жми /buy")
        return
    await update.message.reply_text("🎙️ Слышу твой голосость, легенда! Скоро научусь отвечать на ГС!")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_health, daemon=True).start()
    
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Регистрация команд в меню Telegram при старте приложения
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(set_default_commands(app))
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("buy", buy_premium))
        app.add_handler(CommandHandler("mellstroy", cmd_mellstroy))
        app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        print("БОТ YOKO ЗАПУЩЕН")
        app.run_polling(drop_pending_updates=True)
