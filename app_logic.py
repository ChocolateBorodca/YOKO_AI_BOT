import os
import sqlite3
import logging
from openai import AsyncOpenAI  # Библиотека openai для работы с OpenRouter
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

# Импортируем утилиты из utils.py
from utils import translate_to_burmalda, process_voice_message

YOUR_TELEGRAM_ID = 1151550758

# Настройка постоянного пути для сохранения базы данных на диске Render
DB_FILE = "/app/data/bot_database.db"

# Получаем ключ OpenRouter из настроек сервера
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# Безопасная инициализация клиента OpenRouter
if OPENROUTER_KEY:
    ai_client = AsyncOpenAI(
        base_url="https://openrouter.ai",
        api_key=OPENROUTER_KEY
    )
else:
    ai_client = None
    logging.warning("⚠️ Переменная окружения OPENROUTER_KEY не найдена! Ответы ИИ заблокированы.")

try: 
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: 
    ADMIN_ID = 0

# Словарь для хранения истории сообщений в памяти (для Премиум пользователей)
CONTEXT_MEMORY = {}
MAX_CONTEXT_LEN = 10  # Храним последние 5 реплик пользователя и 5 ответов ИИ

def init_db():
    # Автоматически создаем папку для постоянного диска, если её еще нет на сервере
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    
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
        # Извлечение данных из кортежа sqlite напрямую
        return row[0], row[1]
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
    # Если на сервере нет ключа ИИ, не отправляем запрос в никуда
    if not ai_client:
        return "🔴 Ответ ИИ временно заблокирован: администратор не настроил OPENROUTER_KEY в панели хостинга."

    is_premium, _ = get_user_data(user_id)

    if current_mode == "mellstroy":
        system_prompt = "Ты — Меллстрой, хайповый стример. Говори дерзко, используй сленг: боров, легенда, хайп, суета, крутим слоты. Отвечай кратко, в 1-2 предложениях."
    else:
        system_prompt = "Ты — вежливый и полезный ИИ ассистент по имени YOKO. Отвечай дружелюбно, грамотно и коротко."

    # Управление историей сообщений для Премиум пользователей
    if is_premium:
        if user_id not in CONTEXT_MEMORY:
            CONTEXT_MEMORY[user_id] = []
        CONTEXT_MEMORY[user_id].append({"role": "user", "content": user_text})
        messages_payload = [{"role": "system", "content": system_prompt}] + CONTEXT_MEMORY[user_id]
    else:
        messages_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

    try:
        # Асинхронный стабильный запрос через OpenRouter
        # Модель google/gemini-2.5-flash-ids:free является полностью бесплатной и быстрой
        response = await ai_client.chat.completions.create(
            model="google/gemini-2.5-flash-ids:free",
            messages=messages_payload,
            timeout=15.0
        )
        answer = response.choices.message.content.strip()
        
        if is_premium and answer:
            CONTEXT_MEMORY[user_id].append({"role": "assistant", "content": answer})
            if len(CONTEXT_MEMORY[user_id]) > MAX_CONTEXT_LEN:
                CONTEXT_MEMORY[user_id] = CONTEXT_MEMORY[user_id][-MAX_CONTEXT_LEN:]
                
    except Exception as e:
        answer = f"🔴 Сбой линии связи ИИ: {str(e)[:50]}"

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
    # Передаем ai_client вместо токена Hugging Face для асинхронного распознавания речи
    await process_voice_message(update, context, ai_client, handle_ai_logic, get_user_data)
