import sqlite3
import logging
from telegram import Update
from telegram.ext import ContextTypes

DB_FILE = "yoko_database.db"

# Безопасно получаем ID создателя из настроек Render
try:
    from main import ADMIN_ID
except:
    import os
    try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    except: ADMIN_ID = 0

def init_group_db():
    """Создает таблицу для хранения режимов конкретных групп"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS group_modes (chat_id INTEGER PRIMARY KEY, mode TEXT DEFAULT "default")')
    conn.commit()
    conn.close()

def get_group_mode(chat_id):
    """Узнает, какой режим сейчас активен в группе (yoko или mellstroy)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT mode FROM group_modes WHERE chat_id = ?', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "default"

def set_group_mode_db(chat_id, mode):
    """Записывает новый режим для группы в базу данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO group_modes (chat_id, mode) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET mode=?', (chat_id, mode, mode))
    conn.commit()
    conn.close()

def check_group_premium(user_ids):
    """Проверяет, есть ли среди списка ID хотя бы один Premium-пользователь"""
    if not user_ids: return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    placeholders = ','.join('?' for _ in user_ids)
    cursor.execute(f'SELECT COUNT(*) FROM users WHERE is_premium = 1 AND user_id IN ({placeholders})', user_ids)
    count = cursor.fetchone()
    conn.close()
    return count[0] > 0

async def handle_group_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, handle_ai_logic_func):
    """
    Основная логика работы в группе:
    1. Проверяет участников на наличие Premium. Если никого нет — бот выходит.
    2. Если Premium есть — отвечает в текущем режиме группы (mellstroy или default).
    """
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    user_text = update.message.text

    try:
        # Получаем список админов группы (как срез активных участников)
        chat_admins = await context.bot.get_chat_administrators(chat_id)
        user_ids = [admin.user.id for admin in chat_admins]
        
        # Добавляем создателя бота и автора сообщения в список проверки
        if ADMIN_ID and ADMIN_ID not in user_ids: user_ids.append(ADMIN_ID)
        if user_id not in user_ids: user_ids.append(user_id)
        
        # Проверяем присутствие Premium-боровов
        if not check_group_premium(user_ids):
            await update.message.reply_text(
                "❌ В этой группе нет участников с Premium-подпиской YOKO!\n"
                "Ч ухожу отсюда, боровы. Купите Premium в ЛС у бота!"
            )
            await context.bot.leave_chat(chat_id)
            return
            
        # Если проверка пройдена — берем текущий режим группы и генерируем ответ
        current_mode = get_group_mode(chat_id)
        answer = await handle_ai_logic_func(user_id, user_text, current_mode)
        await update.message.reply_text(answer)
        
    except Exception as e:
        logging.error(f"Ошибка в group_service: {e}")
