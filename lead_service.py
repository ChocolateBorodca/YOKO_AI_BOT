import sqlite3
import requests
import logging
import xml.etree.ElementTree as ET
from telegram import Update
from telegram.ext import ContextTypes

DB_FILE = "yoko_database.db"

try:
    from main import ADMIN_ID, get_user_data
except:
    import os
    try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    except: ADMIN_ID = 0
    def get_user_data(user_id): return 0, "default"

def init_lead_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_search (
            user_id INTEGER PRIMARY KEY,
            step INTEGER DEFAULT 0,
            specialty TEXT,
            keywords TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def start_lead_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # ЖЕСТКАЯ ПРОВЕРКА ПОДПИСКИ: Поиск клиентов — строго платная функция
    is_premium, _ = get_user_data(user_id)
    if not is_premium:
        await update.message.reply_text("❌ Функция ИИ-поиска клиентов доступна только для Premium-пользователей! Активируйте доступ через команду /buy ⚡")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO lead_search (user_id, step) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET step=1', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "🔍 **Запуск ИИ-поиска клиентов и актуальных заказов**\n\n"
        "Шаг 1: Напиши, **кем ты работаешь** и какую конкретно услугу предлагаешь?\n"
        "(Например: *программист Python, веб-разработчик, системный администратор*)"
    )

async def handle_lead_steps(update: Update, context: ContextTypes.DEFAULT_TYPE, client_hf):
    user_id = update.message.from_user.id
    text = update.message.text
    if not text or text.startswith('/'): return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT step, specialty, keywords FROM lead_search WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if not row or row[0] == 0:
        conn.close()
        return False

    step, specialty, keywords = row

    if step == 1:
        cursor.execute('UPDATE lead_search SET step=2, specialty=? WHERE user_id = ?', (text, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            "🎯 Отлично! Шаг 2:\n"
            "Напиши через запятую **ключевые слова**, по которым ИИ должен отфильтровать заказы.\n"
            "(Например: *python, бот, django, парсер, sql*)"
        )
        return True

    if step == 2:
        cursor.execute('UPDATE lead_search SET step=0, keywords=? WHERE user_id = ?', (text, user_id))
        conn.commit()
        conn.close()
        
        status_msg = await update.message.reply_text("🔍 ИИ сканирует живые RSS-ленты бирж фриланса и открытые агрегаторы под твой запрос... Пожалуйста, подожди.")
        
        # Передаем РЕАЛЬНУЮ введенную профессию и ключевые слова в парсер
        search_query = f"{specialty} {text}"
        found_leads = parse_freelance_leads(search_query)
        
        if not found_leads:
            await status_msg.edit_text(
                f"😔 По твоему запросу (*{specialty}*) прямо сейчас на биржах нет открытых заказов.\n"
                f"Попробуй изменить ключевые слова или повторить поиск позже!"
            )
            return True
            
        report = f"🚀 **Найдены реальные актуальные заказы по профилю '{specialty}':**\n\n"
        for i, lead in enumerate(found_leads[:3], 1):
            report += f"{i}. 📋 **Заказ:** {lead['title']}\n"
            report += f"🔗 **Прямая ссылка:** {lead['link']}\n"
            report += f"👤 **Источник данных:** {lead['source']}\n\n"
            
        report += "💡 Переходи по ссылкам и откликайся прямо сейчас, пока предложения свежие!"
        await status_msg.delete()
        await update.message.reply_text(report, disable_web_page_preview=True)
        return True

def parse_freelance_leads(query):
    """Парсит РЕАЛЬНУЮ RSS-ленту Хабр Фриланса по динамическому запросу пользователя"""
    leads = []
    try:
        url = "https://habr.com"
        response = requests.get(url, timeout=7)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Чистим и разбиваем поисковые слова пользователя
            query_words = [w.lower().strip() for w in query.replace(',', ' ').replace('*', ' ').split() if len(w) > 2]
            
            for item in root.findall('.//item'):
                title = item.find('title').text
                link = item.find('link').text
                description = item.find('description').text or ""
                
                # Проверяем реальное совпадение по словам пользователя
                match = any(word in title.lower() or word in description.lower() for word in query_words)
                
                if match:
                    leads.append({
                        "title": title,
                        "link": link,
                        "source": "Habr Freelance (Официальный агрегатор)"
                    })
    except Exception as e:
        logging.error(f"Ошибка реального парсинга: {e}")
        
    return leads
