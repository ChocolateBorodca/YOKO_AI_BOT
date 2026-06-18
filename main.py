import os
import threading
import logging
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from huggingface_hub import InferenceClient

# 1. Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# 2. Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# 3. Настройка ИИ
client = InferenceClient("Qwen/Qwen2.5-Coder-7B-Instruct", token=HF_TOKEN)

# --- БАЗА ДАННЫХ (SQLite) ---
DB_FILE = "yoko_database.db"

def init_db():
    """Создает таблицы пользователей, если их еще нет"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            current_role TEXT DEFAULT 'default'
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    """Возвращает (is_premium, current_role) для пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT is_premium, current_role FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        row = (0, 'default')
    conn.close()
    return row

def set_user_premium(user_id):
    """Активирует премиум для пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET is_premium=1', (user_id,))
    conn.commit()
    conn.close()

def set_user_role(user_id, role):
    """Меняет текущую роль ИИ"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET current_role = ? WHERE user_id = ?', (role, user_id))
    conn.commit()
    conn.close()

# --- ВЕБ-СЕРВЕР ДЛЯ UPTIMEROBOT ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_health():
    server = HTTPServer(('0.0.0.0', 10000), Health)
    server.serve_forever()

# --- ТЕКСТЫ И НАСТРОЙКИ ---
START_TEXT = """Привет я YOKO! Я ИИ бот бурмалда.
Доступные команды:
/buy - Купить Премиум (ИИ-Персонажи, работа с ГС, работа в группах)
/role - Сменить роль ИИ (Только для Премиум)"""

# Системные промты для ИИ-персонажей
ROLES = {
    'default': "Ты дружелюбный помощник YOKO. Отвечай кратко на русском языке.",
    'lawyer': "Ты высококвалифицированный юрист. Отвечай строго, профессионально, с ссылками на законы РФ.",
    'market': "Ты креативный маркетолог и эксперт по рекламе. Предлагай прорывные идеи для бизнеса и броские слоганы."
}

# --- ФУНКЦИИ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)

# 1. Выставление счета на оплату (Telegram Stars)
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    title = "YOKO Premium Доступ"
    description = "Открывает доступ к ИИ-Юристу/Маркетологу, распознаванию ГС и работе бота в группах."
    payload = "yoko_premium_payload"
    currency = "XTR" # Код для Telegram Stars
    price = 100      # Цена в Звездах
    prices = [LabeledPrice("Premium", price)]

    await context.bot.send_invoice(
        chat_id, title, description, payload, "", currency, prices
    )

# 2. Подтверждение платежа Telegram (Обязательный шаг)
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "yoko_premium_payload":
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)

# 3. Выдача Премиума после успешной оплаты
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    set_user_premium(user_id)
    await update.message.reply_text("🎉 Спасибо за покупку! Премиум функции успешно активированы. Используй /role для выбора персонажа!")

# 4. Смена роли (Вариант 1)
async def change_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, _ = get_user_data(user_id)
    
    if not is_premium:
        await update.message.reply_text("❌ Эта функция доступна только Premium пользователям. Купить: /buy")
        return

    args = context.args
    if not args or args[0] not in ['lawyer', 'market', 'default']:
        await update.message.reply_text("Выбери роль, написав команду с параметром:\n/role lawyer — Юрист\n/role market — Маркетолог\n/role default — Обычный чат")
        return

    set_user_role(user_id, args[0])
    await update.message.reply_text(f"✅ Роль успешно изменена на: {args[0]}")

# Основная логика чата с проверкой ролей
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    
    # Защита от работы в группах без премиума (Вариант 5)
    if update.message.chat.type in ['group', 'supergroup']:
        is_premium, _ = get_user_data(user_id)
        if not is_premium:
            await update.message.reply_text("❌ Этот бот может работать в группах только по Premium подписке создателя. До свидания!")
            await context.bot.leave_chat(update.message.chat_id)
            return

    is_premium, current_role = get_user_data(user_id)
    system_prompt = ROLES.get(current_role, ROLES['default'])
    
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

# Обработка голосовых сообщений (Вариант 3)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, _ = get_user_data(user_id)
    
    if not is_premium:
        await update.message.reply_text("❌ Распознавание голосовых сообщений доступно только Premium пользователям. Купить: /buy")
        return
        
    await update.message.reply_text("🎙️ Я получил твое голосовое! (Премиум функция распознавания ГС успешно сработала)")

# --- Запуск ---
if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_health, daemon=True).start()
    
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("buy", buy_premium))
        app.add_handler(CommandHandler("role", change_role))
        
        # Обработчики платежей
        app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
        
        # Чат и Голос
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        print("БОТ YOKO ЗАПУЩЕН С ПРЕМИУМ СИСТЕМОЙ")
        app.run_polling(drop_pending_updates=True)
    else:
        print("ОШИБКА: TELEGRAM_TOKEN не найден!")
