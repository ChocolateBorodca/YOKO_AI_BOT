import os
import sqlite3
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes
from huggingface_hub import InferenceClient

from utils import translate_to_burmalda, process_voice_message

HF_TOKEN = os.getenv("HF_TOKEN")
# ЖЕЛЕЗНЫЙ ШАНС: Переключаемся на вечно живую модель Google Gemma 2
client = InferenceClient("google/gemma-2-2b-it", token=HF_TOKEN)
DB_FILE = "yoko_database.db"

YOUR_TELEGRAM_ID = 1151550758

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0, mode TEXT DEFAULT "default")')
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS group_modes (chat_id INTEGER PRIMARY KEY, mode TEXT DEFAULT "default")')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    if int(user_id) == YOUR_TELEGRAM_ID:
        return 1, "mellstroy"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT is_premium, mode FROM users WHERE user_id = ?', (int(user_id),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 0, "default")', (int(user_id),))
        conn.commit()
        conn.close()
        return 0, "default"
    return int(row[0]), str(row[1])

def get_group_mode(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT mode FROM group_modes WHERE chat_id = ?', (int(chat_id),))
    row = cursor.fetchone()
    conn.close()
    return str(row[0]) if row else "default"

def set_group_mode(chat_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO group_modes (chat_id, mode) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET mode=?', (int(chat_id), str(mode), str(mode)))
    conn.commit()
    conn.close()

def set_user_mode(user_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET mode = ? WHERE user_id = ?', (str(mode), int(user_id)))
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)', (int(user_id), str(role), str(content)))
    conn.commit()
    conn.close()

def get_chat_history(user_id, limit=6):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT ?', (int(user_id), limit))
    rows = cursor.fetchall()
    conn.close()
    history = []
    for row in reversed(rows):
        history.append({"role": str(row[0]), "content": str(row[1])})
    return history

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_info = (
         "🚀 **Привет я YOKO! Я универсальный ИИ-ассистент.**\n\n"
         "Вот список всех доступных команд проекта:\n"
         "😇 /yoko — Обычный вежливый ИИ (Бесплатно)\n"
         "⚡ /buy — Открыть расширенный Премиум доступ за 15 звезд\n"
         "🎰 /mellstroy — Вернуть режим Меллстроя (Если куплен)\n"
         "📋 /profile — Посмотреть свой ID и статус подписки"
    )
    await update.message.reply_text(start_info, parse_mode="Markdown")

async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        set_group_mode(update.message.chat_id, "default")
        await update.message.reply_text("😇 Групповой режим успешно изменен на обычный ИИ YOKO.")
        return
    set_user_mode(update.message.from_user.id, "default")
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
    except Exception as e: logging.error(f"Ошибка счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        set_group_mode(update.message.chat_id, "mellstroy")
        await update.message.reply_text("🎰 МЕЛЛСТРОЙ В ЧАТЕ! Включен язык Бурмалда для всей группы. 🔥")
        return
    is_premium, _ = get_user_data(update.message.from_user.id)
    if not is_premium:
        await update.message.reply_text("❌ Сначала нужно открыть Премиум-режим через команду /buy ⚡")
        return
    set_user_mode(update.message.from_user.id, "mellstroy")
    await update.message.reply_text("🔥 МЕЛЛСТРОЙ ВЕРНУЛСЯ! Ч снова общаюсь на языке Бурмалда. 🎰")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data(user_id)
    status_str = "Активирован (Premium)" if is_premium else "Не активирован"
    mode_str = "Меллстроевский (Бурмалда)" if current_mode == "mellstroy" else "Обычный YOKO"
    await update.message.reply_text(f"📋 ТВОЙ ПРОФИЛЬ:\n• ID: {user_id}\n• Премиум: {status_str}\n• Текущий режим: {mode_str}")

async def handle_ai_logic(user_id, user_text, current_mode):
    prompt = "Ты — Меллстрой. Твой стиль: хайповый, дерзкий. Используй: боров, легенда, крутим слоты. Отвечай кратко." if current_mode == "mellstroy" else "Ты дружелюбный ИИ. Отвечай кратко."
    save_message(user_id, "user", user_text)
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_text}]
    try:
        response = client.chat_completion(messages=messages, max_tokens=150)
        answer = ""
        if isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                answer = response['choices']['message']['content']
            elif 'message' in response:
                answer = response['message']['content']
        elif isinstance(response, list) and len(response) > 0:
            item = response
            if isinstance(item, dict) and 'message' in item:
                answer = item['message'].get('content', '')
        else:
            try: answer = response.choices.message.content
            except:
                try: answer = response.choices.message.content
                except: answer = str(response)

        if not answer: answer = str(response)
        save_message(user_id, "assistant", answer)
        if current_mode == "mellstroy": answer = translate_to_burmalda(answer)
        return answer
    except Exception as e: return f"🔴 Ошибка ИИ: {str(e)[:40]}"

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    if update.message.chat.type in ['group', 'supergroup']:
        current_mode = get_group_mode(update.message.chat_id)
        await update.message.reply_text(await handle_ai_logic(user_id, user_text, current_mode))
        return
    is_premium, current_mode = get_user_data(user_id)
    await update.message.reply_text(await handle_ai_logic(user_id, user_text, current_mode))

async def handle_voice_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_voice_message(update, context, HF_TOKEN, handle_ai_logic, get_user_data)
