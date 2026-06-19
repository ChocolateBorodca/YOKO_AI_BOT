import os
import sqlite3
import random
import logging
from telegram.ext import ContextTypes

DB_FILE = "yoko_database.db"

try:
    from main import ADMIN_ID, client, handle_ai_logic
except:
    # Запасной импорт на случай, если функции еще не импортированы наружу
    ADMIN_ID = 0

def init_sueta_db():
    """Создает таблицу для запоминания активных групп, куда зашел бот"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS active_groups (chat_id INTEGER PRIMARY KEY)')
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка создания базы суеты: {e}")

def register_group_for_sueta(chat_id):
    """Добавляет группу в список для случайных врывов Меллстроя"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO active_groups (chat_id) VALUES (?) ON CONFLICT(chat_id) DO NOTHING', (chat_id,))
        conn.commit()
        conn.close()
    except:
        pass

async def random_sueta_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Фоновая задача: подкидывает кубик и с шансом 30% 
    сама пишет угарную фразу от Меллстроя в случайный чат пацанам!
    """
    # Шанс 30%, чтобы бот не спамил каждую минуту, а врывался неожиданно
    if random.random() > 0.3:
        return 
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT chat_id FROM active_groups')
        groups = cursor.fetchall()
        conn.close()
        
        if not groups:
            return
            
        # Выбираем случайный чат из списка активных
        target_chat = random.choice(groups)[0]
        
        # Список угарных тем, на которые Меллстрой зайдет сам
        random_prompts = [
            "Выдай жесткую угарную фразу для чата, поприветствуй всех боровов и спроси че за суета.",
            "Скажи всем в чате, что ты даешь лям баксов тому, кто прямо сейчас пойдет и покрутит слоты.",
            "Эмоционально крикни капсом, что ты осуждаю тишину в этом чате и требуешь хайпа.",
            "Скажи пацанам, что они все легенды, и спроси как дела у их додов и жинок."
        ]
        prompt = random.choice(random_prompts)
        
        # Генерируем ответ через твою стандартную ИИ логику
        # Если функция handle_ai_logic доступна в main.py, берем её
        from main import handle_ai_logic
        answer = await handle_ai_logic(target_chat, prompt, "mellstroy")
        
        # Отправляем сообщение в выбранную группу
        await context.bot.send_message(chat_id=target_chat, text=answer)
        
    except Exception as e:
        logging.error(f"Ошибка в работе random_sueta_job: {e}")
