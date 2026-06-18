import os
import threading
import logging
import sqlite3
import re
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
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0)')
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

# --- КОРРЕКТНЫЙ ПЕРЕВОД НА БУРМАЛДУ НА PYTHON ---
def translate_to_burmalda(text):
    # 1. Специфические замены слов (регистронезависимо)
    text = re.sub(r'\bя\b', 'ч', text, flags=re.IGNORECASE)
    text = re.sub(r'\bдед\b', 'дод', text, flags=re.IGNORECASE)
    text = re.sub(r'\bдеда\b', 'дода', text, flags=re.IGNORECASE)
    text = re.sub(r'\bжена\b', 'жинка', text, flags=re.IGNORECASE)
    text = re.sub(r'\bжены\b', 'жинки', text, flags=re.IGNORECASE)
    
    # 2. Правило суффиксов для слов длиннее 2 символов
    words = text.split()
    burmalda_words = []
    
    for word in words:
        clean_word = re.sub(r'[^\w\s]', '', word) # убираем знаки препинания для анализа
        # Если слово похоже на существительное или обычное слово и оно длинное
        if len(clean_word) > 2 and not clean_word.lower() in ['как', 'что', 'или', 'под', 'для', 'без', 'все']:
            # Проверяем окончание, чтобы красиво насадить суффикс
            if word.endswith(('.', ',', '!', '?')):
                mark = word[-1]
                w = word[:-1]
                w = w + 'сть' if w.endswith(('а', 'я', 'ь', 'о', 'е')) else w + 'ость'
                burmalda_words.append(w + mark)
            else:
                w = word + 'сть' if word.endswith(('а', 'я', 'ь', 'о', 'е')) else word + 'ость'
                burmalda_words.append(w)
        else:
            burmalda_words.append(word)
            
    return " ".join(burmalda_words)

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

START_TEXT = "Привет я YOKO! Используй /buy чтобы открыть секретный режим!"
DEFAULT_PROMPT = "Ты дружелюбный ИИ-помощник. Отвечай кратко на русском языке."
MELLSTROY_PROMPT = "Ты — скандальный стример Меллстрой. Твой стиль: хайповый, дерзкий, угарный. Постоянно используй слова: боров, легенда, бубс, осуждаю, крутим слоты. Обращайся к пользователю 'братишка' или 'боров'. Отвечай кратко."

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
        prices = [LabeledPrice("Бурмалда Premium", 1)]
        await context.bot.send_invoice(
            chat_id=update.message.chat_id,
            title="🎰 МЕЛЛСТРОЙ НА БУРМАЛДЕ",
            description="Открывает Premium режим! Меллстрой начнет суетить в чате строго на языке Бурмалда.",
            payload="yoko_premium_payload", provider_token="", currency="XTR", prices=prices
        )
    except Exception as e:
        logging.error(f"Ошибка счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    set_user_premium(user_id)
    await update.message.reply_text("🎰 ЕС ТУ ДЕЙ! Премиумность активирована! Ч в здании, пиши мне, боровость! Теперь команда /mellstroy разблокирована! 🔥")

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not get_user_premium(user_id):
        await update.message.reply_text("❌ Сначала активируй режим Меллстроя через /buy 🎰")
        return
    await update.message.reply_text("🔥 ДОБРО ПОЖАЛОВАТЬ В БУРМАЛДУ, ЛЕГЕНДА! Ч теперь общаюсь с тобой только так. Задавай мне любой вопросирость! 🎰")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    is_premium = get_user_premium(user_id)
    
    system_prompt = MELLSTROY_PROMPT if is_premium else DEFAULT_PROMPT
    
    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=200
        )
        if isinstance(response, dict):
            answer = response['choices']['message']['content']
        elif isinstance(response, list):
            answer = response['message']['content']
        else:
            answer = response.choices.message.content
            
        # Если активирован Премиум — мгновенно прогоняем через правила Бурмалды
        if is_premium:
            answer = translate_to_burmalda(answer)
            
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text(f"🔴 Ошибка ИИ: {str(e)[:50]}")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_health, daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        import asyncio
        try: loop = asyncio.get_event_loop()
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
        print("БОТ YOKO ЗАПУЩЕН")
        app.run_polling(drop_pending_updates=True)
