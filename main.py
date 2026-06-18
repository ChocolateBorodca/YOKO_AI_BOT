import os
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from huggingface_hub import InferenceClient

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

client = InferenceClient("Qwen/Qwen2.5-Coder-7B-Instruct", token=HF_TOKEN)

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

START_TEXT = "Привет я YOKO! Чтобы протестировать оплату, введи /buy"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)

# Команда покупки Звезд
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        prices = [LabeledPrice("YOKO Premium", 100)] # 100 Звезд
        
        await context.bot.send_invoice(
            chat_id=chat_id,
            title="YOKO Premium",
            description="Доступ к платным функциям ИИ",
            payload="yoko_payload",
            provider_token="", # Для Telegram Stars оставляем ПУСТЫМ
            currency="XTR",   # Код Звезд
            prices=prices
        )
    except Exception as e:
        logging.error(f"Ошибка выставления счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Оплата прошла успешно! Премиум активирован (тестовый режим).")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": "Ты дружелюбный помощник YOKO."},
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

if __name__ == '__main__':
    threading.Thread(target=run_health, daemon=True).start()
    
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("buy", buy_premium))
        app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        
        print("БОТ ЗАПУЩЕН")
        app.run_polling(drop_pending_updates=True)
