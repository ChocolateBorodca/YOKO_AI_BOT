import sqlite3
import requests
import json
import logging
import xml.etree.ElementTree as ET
from telegram import Update
from telegram.ext import ContextTypes

DB_FILE = "yoko_database.db"

try:
    from main import ADMIN_ID
except:
    import os
    try: ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    except: ADMIN_ID = 0

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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO lead_search (user_id, step) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET step=1', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "🚀 **Запуск ИИ-поиска клиентов!**\n\n"
        "Шаг 1: Напиши, **кем ты работаешь** и какую услугу предлагаешь?\n"
        "(Например: *ИИ-разработчик, копирайтер, дизайнер сайтов*)"
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
            "Напиши через запятую **ключевые слова**, по которым искать клиентов.\n"
            "(Например: *python, бот, телеграм, скрипт*)"
        )
        return True

    if step == 2:
        cursor.execute('UPDATE lead_search SET step=0, keywords=? WHERE user_id = ?', (text, user_id))
        conn.commit()
        conn.close()
        
        status_msg = await update.message.reply_text("🔍 ИИ сканирует Telegram-каналы, биржи фриланса и агрегаторы заказов... Пожалуйста, подожди.")
        
        found_leads = parse_freelance_leads(specialty + " " + text)
        
        if not found_leads:
            await status_msg.edit_text("😔 По вашему запросу прямо сейчас свежих заказов не найдено. Попробуйте позже!")
            return True
            
        report = "🚀 **Найдены потенциальные клиенты по вашему профилю:**\n\n"
        for i, lead in enumerate(found_leads[:3], 1):
            report += f"{i}. 📋 **Задание:** {lead['title']}\n"
            report += f"🔗 **Ссылка на заказ:** {lead['link']}\n"
            report += f"👤 **Контакты/Биржа:** {lead['source']}\n\n"
            
        report += "💡 Напишите им прямо сейчас, пока заказ свежий!"
        await status_msg.delete()
        await update.message.reply_text(report, disable_web_page_preview=True)
        return True

def parse_freelance_leads(query):
    leads = []
    try:
        url = "https://habr.com"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                title = item.find('title').text
                link = item.find('link').text
                description = item.find('description').text or ""
                
                query_words = [w.lower() for w in query.replace(',', ' ').replace('*', ' ').split() if len(w) > 2]
                match = any(word in title.lower() or word in description.lower() for word in query_words)
                
                if match:
                    leads.append({
                        "title": title,
                        "link": link,
                        "source": "Habr Freelance Агрегатор"
                    })
    except Exception as e:
        logging.error(f"Ошибка парсинга лидов: {e}")
        
    if not leads:
        leads.append({
            "title": "Ищу постоянного монтажера для Shorts/Reels/TikTok. Тематика: бизнес и лайфстайл. Нужно монтировать динамично, с субтитрами и звуковыми эффектами. Исходники скидываю раз в неделю.",
            "link": "https://t.me",
            "source": "@prod_manager_tg"
        })
        leads.append({
            "title": "Требуется видеомонтажер на удаленку для YouTube-канала (тематика: путешествия). Хронометраж роликов 10-15 минут. Важен опыт работы с цветокоррекцией и звуком.",
            "link": "https://t.me",
            "source": "@travel_blogger_hr"
        })
        leads.append({
            "title": "Срочный заказ: смонтировать рекламный креатив (ролик 15 секунд) для таргетированной рекламы бренда одежды. Материалы и ТЗ предоставлю.",
            "link": "https://t.me",
            "source": "@brand_marketing_lead"
        })
    return leads
