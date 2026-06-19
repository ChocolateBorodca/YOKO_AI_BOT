import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters

import app_logic

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

async def set_default_commands(application):
    commands = [
        BotCommand("start", "Запустить бота и увидеть команды"),
        BotCommand("profile", "👑 Твой статус (Нормальный русский)"),
        BotCommand("yoko", "😇 Обычный ИИ (Бесплатно)"),
        BotCommand("buy", "⚡ Купить Премиум функции (15 звезд)"),
        BotCommand("mellstroy", "🎰 Включить режим МЕЛЛСТРОЯ")
    ]
    await application.bot.set_my_commands(commands)

if __name__ == '__main__':
    app_logic.init_db()
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), Health).serve_forever(), daemon=True).start()
    if TELEGRAM_TOKEN:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        import asyncio
        try: loop = asyncio.get_event_loop()
        except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        loop.run_until_complete(set_default_commands(app))
        app.add_handler(CommandHandler("start", app_logic.start))
        app.add_handler(CommandHandler("yoko", app_logic.cmd_yoko))
        app.add_handler(CommandHandler("buy", app_logic.buy_premium))
        app.add_handler(CommandHandler("mellstroy", app_logic.cmd_mellstroy))
        app.add_handler(CommandHandler("profile", app_logic.cmd_profile))
        app.add_handler(PreCheckoutQueryHandler(app_logic.precheckout_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, app_logic.chat))
        app.add_handler(MessageHandler(filters.VOICE, app_logic.handle_voice_gateway))
        app.run_polling(drop_pending_updates=True)
