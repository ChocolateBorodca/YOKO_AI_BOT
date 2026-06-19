import re
import io
import sqlite3
import requests

DB_FILE = "yoko_database.db"

def init_memory_db():
    """Создает таблицу для хранения истории сообщений"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    """Сохраняет сообщение в историю"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)', (user_id, role, content))
    conn.commit()
    conn.close()

def get_chat_history(user_id, limit=6):
    """Возвращает последние сообщения диалога для ИИ"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT ?', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Разворачиваем историю в хронологическом порядке
    history = []
    for role, content in reversed(rows):
        history.append({"role": role, "content": content})
    return history

def translate_to_burmalda(text):
    text = re.sub(r'\bя\b', 'ч', text, flags=re.IGNORECASE)
    text = re.sub(r'\bдед\b', 'дод', text, flags=re.IGNORECASE)
    text = re.sub(r'\bдеда\b', 'дода', text, flags=re.IGNORECASE)
    text = re.sub(r'\bжена\b', 'жинка', text, flags=re.IGNORECASE)
    text = re.sub(r'\bжены\b', 'жинки', text, flags=re.IGNORECASE)
    
    words = text.split()
    burmalda_words = []
    for word in words:
        clean_word = re.sub(r'[^\w\s]', '', word)
        if len(clean_word) > 2 and not clean_word.lower() in ['как', 'что', 'или', 'под', 'для', 'без', 'все']:
            if word.endswith(('.', ',', '!', '?')):
                mark = word[-1]
                w = word[:-1]
                w = w + 'сть' if w.endswith(('а', 'я', 'ь', 'о', 'е')) else w + 'ость'
                burmalda_words.append(w + mark)
            else:
                w = word + 'сть' if word.endswith(('а', 'я', 'ь', 'о', 'е')) else word + 'ость'
                burmalda_words.append(w)
        else:
            burmalda_words.append(word)
    return " ".join(burmalda_words)

def transcribe_audio(audio_bytes, hf_token):
    try:
        API_URL = "https://huggingface.co"
        headers = {"Authorization": f"Bearer {hf_token}"}
        response = requests.post(API_URL, headers=headers, data=audio_bytes)
        return response.json().get("text", "")
    except:
        return ""
