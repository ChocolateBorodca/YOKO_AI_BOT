import os
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from huggingface_hub import InferenceClient

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Ключи из настроек Environment на Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ИИ модель (Qwen 2.5)
client = InferenceClient("Qwen/Qwen2.5-72B-Instruct", token=HF_TOKEN)

# Веб-сервер для Render (порт 10000)
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

def run_health():
    server = HTTPServer(('0.0.0.0', 10000), Health)
    server.serve_forever()

START_TEXT = """Привет я YOKO! С помощью меня сможешь узнать как установить YOKO на телефон. 
Пока что это работает в виде сайта, чтобы можно было зайти и на Android, и на iPhone. 

Как сделать как приложение: 
1. Открой ссылку через Google Chrome 
2. Нажми на 3 точки сверху 
3. Выбери "Добавить на главный экран" 
Теперь сайт будет как приложение)"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logging.info(f"Запрос от пользователя: {user_text}")
    
    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": "Ты дружелюбный помощник YOKO. Отвечай кратко на русском языке."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=500
        )
        # ИСПРАВЛЕННЫЙ ПУТЬ К ОТВЕТУ:
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        await update.message.reply_text("Я немного задумался, напиши чуть позже!")

if __name__ == '__main__':
    threading.Thread(target=run_health, daemon=True).start()
    
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        print("БОТ YOKO ЗАПУЩЕН")
        app.run_polling(drop_pending_updates=True)
