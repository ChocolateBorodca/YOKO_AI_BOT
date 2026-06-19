import os
import threading
import logging
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, LabeledPrice, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters
)

from huggingface_hub import InferenceClient
from utils import translate_to_burmalda, transcribe_audio
from photo_service import generate_flux_image

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except:
    ADMIN_ID = 0

client = InferenceClient(
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    token=HF_TOKEN
)

DB_FILE = "yoko_database.db"


# ================= DB =================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'default'
        )
    """)
    conn.commit()
    conn.close()


def get_user_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT is_premium, mode FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if ADMIN_ID != 0 and user_id == ADMIN_ID:
        conn.close()
        if not row:
            return 1, "mellstroy"
        return 1, row[1]

    if not row:
        cur.execute(
            "INSERT INTO users (user_id, is_premium, mode) VALUES (?, 0, 'default')",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return 0, "default"

    conn.close()
    return row


def set_user_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (user_id, is_premium, mode)
        VALUES (?, 1, 'mellstroy')
        ON CONFLICT(user_id)
        DO UPDATE SET is_premium=1, mode='mellstroy'
    """, (user_id,))

    conn.commit()
    conn.close()


def set_user_mode(user_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (user_id, mode)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET mode=excluded.mode
    """, (user_id, mode))

    conn.commit()
    conn.close()


# ================= WEB =================

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я YOKO 🤖\n"
        "/yoko — обычный режим\n"
        "/buy — премиум\n"
        "/mellstroy — режим Mellstroy\n"
        "/photo — генерация фото\n"
        "/profile — профиль"
    )


async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_mode(update.message.from_user.id, "default")
    await update.message.reply_text("Обычный режим включен 😇")


async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = [LabeledPrice("Premium", 15)]
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Premium YOKO",
        description="Unlock Mellstroy mode",
        payload="premium_payload",
        provider_token="",
        currency="XTR",
        prices=prices
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_premium(update.message.from_user.id)
    await update.message.reply_text("🔥 Premium активирован!")


async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, _ = get_user_data(user_id)

    if not is_premium:
        await update.message.reply_text("❌ Купи премиум /buy")
        return

    set_user_mode(user_id, "mellstroy")
    await update.message.reply_text("🔥 MELLSTROY MODE ON")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, mode = get_user_data(user_id)

    await update.message.reply_text(
        f"ID: {user_id}\n"
        f"Premium: {is_premium}\n"
        f"Mode: {mode}"
    )


async def cmd_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, mode = get_user_data(user_id)

    if not is_premium:
        await update.message.reply_text("❌ Premium only")
        return

    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Напиши запрос")
        return

    msg = await update.message.reply_text("Генерирую фото... 🎨")

    photo = generate_flux_image(prompt, client)

    if not photo:
        await msg.edit_text("❌ Ошибка генерации")
        return

    await msg.delete()
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photo,
        caption="Готово 🔥" if mode == "mellstroy" else "Image generated ✨"
    )


# ================= AI =================

async def ai(user_text, mode):
    system = (
        "Ты Меллстрой. Дерзкий стиль, короткие ответы."
        if mode == "mellstroy"
        else "Ты дружелюбный AI."
    )

    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text}
            ],
            max_tokens=200
        )

        answer = response.choices[0].message.content

        if mode == "mellstroy":
            answer = translate_to_burmalda(answer)

        return answer

    except Exception as e:
        return f"Error: {str(e)[:50]}"


# ================= CHAT =================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    _, mode = get_user_data(user_id)

    text = update.message.text
    answer = await ai(text, mode)

    await update.message.reply_text(answer)


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, mode = get_user_data(user_id)

    if not is_premium:
        await update.message.reply_text("Premium only")
        return

    file = await context.bot.get_file(update.message.voice.file_id)
    audio = await file.download_as_bytearray()

    text = transcribe_audio(bytes(audio), HF_TOKEN)

    if not text:
        await update.message.reply_text("Не понял голос")
        return

    answer = await ai(text, mode)
    await update.message.reply_text(answer)


# ================= MAIN =================

if __name__ == "__main__":
    init_db()

    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", 10000), Health).serve_forever(),
        daemon=True
    ).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        app.bot.set_my_commands([
            BotCommand("start", "Start"),
            BotCommand("yoko", "AI"),
            BotCommand("buy", "Premium"),
            BotCommand("mellstroy", "Mode"),
            BotCommand("photo", "Image"),
            BotCommand("profile", "Profile")
        ])
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yoko", cmd_yoko))
    app.add_handler(CommandHandler("buy", buy_premium))
    app.add_handler(CommandHandler("mellstroy", cmd_mellstroy))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("photo", cmd_photo))

    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.VOICE, voice))

    app.run_polling(drop_pending_updates=True)
