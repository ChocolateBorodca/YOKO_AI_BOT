import os
import sqlite3
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes
from huggingface_hub import InferenceClient

from utils import translate_to_burmalda, transcribe_audio, init_memory_db, save_message, get_chat_history
from group_service import init_group_db, handle_group_chat, set_group_mode_db
from sueta_service import init_sueta_db, register_group_for_sueta, random_sueta_job
from lead_service import init_lead_db, start_lead_search, handle_lead_steps

HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient("Qwen/Qwen2.5-Coder-7B-Instruct", token=HF_TOKEN)
DB_FILE = "yoko_database.db"

try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except: ADMIN_ID = 0

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0, mode TEXT DEFAULT "default")')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    if ADMIN_ID != 0 and int(user_id) == ADMIN_ID:
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

def set_user_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 1, "mellstroy") ON CONFLICT(user_id) DO UPDATE SET is_premium=1, mode="mellstroy"', (int(user_id),))
    conn.commit()
    conn.close()

def set_user_mode(user_id, mode):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (user_id, is_premium, mode) VALUES (?, 1, ?) ON CONFLICT(user_id) DO UPDATE SET mode=?', (int(user_id), str(mode), str(mode)))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_info = (
         "Привет я YOKO! Я ИИ бот-помощник.\n\n"
         "Вот список всех доступных команд:\n"
         "/yoko — Обычный вежливый ИИ (Бесплатно)\n"
         "/buy — Открыть расширенный Премиум доступ за 15 звезд\n"
         "/mellstroy — Вернуть режим Меллстроя (Если куплен)\n"
         "/find_clients — ИИ-поиск актуальных заказов и клиентов из сети\n"
         "/profile — Посмотреть свой статус подписки"
    )
    await update.message.reply_text(start_info)

async def cmd_yoko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        set_group_mode_db(update.message.chat_id, "default")
        await update.message.reply_text("😇 Групповой режим успешно изменен на обычный ИИ YOKO.")
        return
    set_user_mode(update.message.from_user.id, "default")
    await update.message.reply_text("😇 Теперь с тобой общается обычный ИИ YOKO.")

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prices = [LabeledPrice("Премиум доступ YOKO AI", 15)]
        await context.bot.send_invoice(
            chat_id=update.message.chat_id, 
            title="⚡ YOKO AI — Премиум функции",
            description="Активация расширенного ИИ-функционала: безлимитный анализ ГС, работа ИИ ассистента в группах, глубокая память диалога и модуль ИИ-поиска клиентов.", 
            payload="yoko_premium_payload", provider_token="", currency="XTR", prices=prices
        )
    except Exception as e: logging.error(f"Ошибка счета: {e}")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_premium(update.message.from_user.id)
    await update.message.reply_text("⚡ Премиум-доступ успешно активирован! Все расширенные и поисковые ИИ-функции разблокированы.")

async def cmd_mellstroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type in ['group', 'supergroup']:
        set_group_mode_db(update.message.chat_id, "mellstroy")
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
    messages = [{"role": "system", "content": prompt}]
    history = get_chat_history(user_id, limit=6)
    messages.extend(history)
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
            except: answer = str(response)

        if not answer: answer = str(response)
        save_message(user_id, "assistant", answer)
        if current_mode == "mellstroy": answer = translate_to_burmalda(answer)
        return answer
    except Exception as e: return f"🔴 Ошибка ИИ: {str(e)[:40]}"

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_searching = await handle_lead_steps(update, context, client)
    if is_searching: return
    if update.message.chat.type in ['group', 'supergroup']:
        register_group_for_sueta(update.message.chat_id)
        await handle_group_chat(update, context, handle_ai_logic)
        return
    user_text = update.message.text
    is_premium, current_mode = get_user_data(user_id)
    await update.message.reply_text(await handle_ai_logic(user_id, user_text, current_mode))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data(user_id)
    if not is_premium:
        await update.message.reply_text("❌ ГС доступно только Premium пользователям.")
        return
    await update.message.reply_text("🎙️ Расшифровываю голосовое...")
    file = await context.bot.get_file(update.message.voice.file_id)
    audio = await file.download_as_bytearray()
    text = transcribe_audio(bytes(audio), os.getenv("HF_TOKEN"))
    if not text:
        await update.message.reply_text("❌ Не удалось разобрать слова.")
        return
    answer = await handle_ai_logic(user_id, text, current_mode)
    await update.message.reply_text(f"💬 Вы: {text}\n\n🤖 Ответ: {answer}")
