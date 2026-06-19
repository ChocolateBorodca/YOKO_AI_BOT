import os
import threading
import logging
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, LabeledPrice, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from huggingface_hub import InferenceClient
from utils import translate_to_burmalda, transcribe_audio

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: ADMIN_ID = 0

client = InferenceClient("Qwen/Qwen2.5-Coder-7B-Instruct", token=HF_TOKEN)
DB_FILE = "yoko_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0, mode TEXT DEFAULT "default")')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT is_premium, mode FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    # ИСПРАВЛЕНО: для создателя всегда Премиум=1, но режим берётся настоящий из базы данных
    if ADMIN_ID != 0 and user_id == ADMIN_ID:
        if not row:
            return 1, "mellstroy"
        return 1, row[1]
        
    if not row:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 0, "default")', (user_id,))
        conn.commit()
        conn.close()
        return 0, "default"
    return row[0], row[1]

def set_user_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 1, "mellstroy") ON CONFLICT(user_id) DO UPDATE SET is_premium=1, mode="mellstroy"', (user_id,))
    conn.commit()
    conn.close()

def set_user_mode(user_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 1, ?) ON CONFLICT(user_id) DO UPDATE SET mode=?', (user_id, mode, mode))
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

async def set_default_commands(application):
    commands = [
        BotCommand("start", "Запустить бота и увидеть команды"),
        BotCommand("profile", "👑 Твой статус (Нормальный русский)"),
        BotCommand("yoko", "😇 Обычный ИИ (Бесплатно)"),
        BotCommand("buy", "⚡ Купить режим МЕЛЛСТРОЯ (1 звезда)"),
        BotCommand("mellstroy", "🎰 Включить режим МЕЛЛСТРОЯ")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_info = (
        "Привет я YOKO! Я ИИ бот бурмалда.\n\n"
        "Вот список всех доступных команд, нажми на любую:\n"
        "/yoko — Переключить на обычный вежливый ИИ (Бесплатно)\n"
        "/buy — Открыть платный режим МЕЛЛСТРОЯ за 1 звезду\n"
        "/mellstroy — Включить режим Меллстроя обратно\n"
        "/profile — Посмотреть свой ID и статус подписки"
    )
    await update.message.reply_text(start_info)

async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    set_user_mode(user_id, "default")
    await update.message.reply_text("😇 Теперь с тобой общается обычный ИИ YOKO.")

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prices = [LabeledPrice("Бурмалда Premium", 1)]
        await context.bot.send_invoice(
            chat_id=update.message.chat_id, title="🎰 МЕЛЛСТРОЙ НА БУРМАЛДЕ",
            description="Открывает Premium режим!", payload="yoko_premium_payload",
            provider_token="", currency="XTR", prices=prices
        )
    except Exception as e: logging.error(f"Ошибка счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_premium(update.message.from_user.id)
    await update.message.reply_text("🎰 Премиумность активирована! Режим Меллстроя-Бурмалды включен! 🔥")

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, _ = get_user_data(user_id)
    if not is_premium:
        await update.message.reply_text("❌ Сначала нужно открыть этот режим через /buy 🎰")
        return
    set_user_mode(user_id, "mellstroy")
    await update.message.reply_text("🔥 МЕЛЛСТРОЙ ВЕРНУЛСЯ! Ч снова общаюсь на языке Бурмалда. 🎰")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data(user_id)
    status_str = "Активирован (Premium)" if is_premium else "Не активирован"
    mode_str = "Меллстроевский (Бурмалда)" if current_mode == "mellstroy" else "Обычный YOKO"
    await update.message.reply_text(f"📋 ТВОЙ ПРОФИЛЬ:\n• ID: {user_id}\n• Премиум: {status_str}\n• Текущий режим: {mode_str}")

async def handle_ai_logic(user_text, current_mode):
    prompt = "Ты — Меллстрой. Твой стиль: хайповый, дерзкий. Используй: боров, легенда, крутим слоты. Отвечай кратко." if current_mode == "mellstroy" else "Ты дружелюбный ИИ. Отвечай кратко."
    try:
        response = client.chat_completion(messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_text}], max_tokens=150)
        
        answer = ""
        try:
            answer = response.choices.message.content
        except:
            if isinstance(response, list) and len(response) > 0:
                item = response[0]
                if isinstance(item, dict) and 'message' in item:
                    answer = item['message'].get('content', '')
            elif isinstance(response, dict):
                if 'choices' in response and len(response['choices']) > 0:
                    answer = response['choices'][0]['message'].get('content', '')
                elif 'message' in response:
                    answer = response['message'].get('content', '')

        if not answer:
            answer = str(response)

        if current_mode == "mellstroy": 
            answer = translate_to_burmalda(answer)
        return answer
    except Exception as e: return f"🔴 Ошибка ИИ: {str(e)[:40]}"

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    if update.message.chat.type in ['group', 'supergroup']:
        is_premium, current_mode = get_user_data(user_id)
        if not is_premium:
            await update.message.reply_text("❌ Только для Премиум пользователей.")
            await context.bot.leave_chat(update.message.chat_id)
            return
        await update.message.reply_text(await handle_ai_logic(user_text, current_mode))
        return
    is_premium, current_mode = get_user_data(user_id)
    await update.message.reply_text(await handle_ai_logic(user_text, current_mode))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data(user_id)
    if not is_premium:
        await update.message.reply_text("❌ ГС доступно только Premium пользователям.")
        return
    await update.message.reply_text("🎙️ Расшифровываю голосовое...")
    file = await context.bot.get_file(update.message.voice.file_id)
    audio = await file.download_as_bytearray()
    text = transcribe_audio(bytes(audio), HF_TOKEN)
    if not text:
        await update.message.reply_text("❌ Не удалось разобрать слова.")
        return
    answer = await handle_ai_logic(text, current_mode)
    await update.message.reply_text(f"💬 Вы: {text}\n\n🤖 Ответ: {answer}")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), Health).serve_forever(), daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        import asyncio
        try: loop = asyncio.get_event_loop()
        except: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        loop.run_until_complete(set_default_commands(app))
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("yoko", cmd_yoko))
        app.add_handler(CommandHandler("buy", buy_premium))
        app.add_handler(CommandHandler("mellstroy", cmd_mellstroy))
        app.add_handler(CommandHandler("profile", cmd_profile))
        app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app.run_polling(drop_pending_updates=True)
