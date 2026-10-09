import re
import io
import logging

def translate_to_burmalda(text):
    """Словарь перевода обычного текста в язык Бурмалды"""
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

async def process_voice_message(update, context, ai_client, handle_ai_logic_func, get_user_data_func):
    """ИСПРАВЛЕНО: Полностью асинхронная расшифровка ГС через OpenRouter вместо Hugging Face"""
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data_func(user_id)
    
    if not is_premium:
        await update.message.reply_text("❌ Функция работы с ГС доступна только Premium пользователям! Жми /buy ⚡")
        return
        
    if not ai_client:
        await update.message.reply_text("🔴 ИИ временно недоступен: администратор не настроил OPENROUTER_KEY.")
        return
        
    await update.message.reply_text("🎙️ Изучаю твою аудиозапись, подожди...")
    try:
        # Скачиваем файл из Telegram в память
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_data = await file.download_as_bytearray()
        
        # Создаем файлоподобный объект в памяти для отправки в API
        audio_file = io.BytesIO(bytes(audio_data))
        audio_file.name = "voice.ogg"  # Telegram записывает голосовые в формате OGG
        
        # Вызываем официальное распознавание речи (Whisper) через OpenRouter
        transcript = await ai_client.audio.transcriptions.create(
            model="openai/whisper-large-v3",
            file=audio_file
        )
        
        text = transcript.text.strip() if hasattr(transcript, 'text') else str(transcript).strip()
        
        if not text:
            await update.message.reply_text("❌ Не удалось разобрать слова. Попробуй сказать четче.")
            return
            
        # Отправляем полученный текст в наш ИИ-мозг
        answer = await handle_ai_logic_func(user_id, text, current_mode)
        await update.message.reply_text(f"💬 Расшифровка ГС:\n«{text}»\n\n🤖 Ответ ИИ:\n{answer}")
        
    except Exception as e:
        logging.error(f"Ошибка обработки ГС: {e}")
        await update.message.reply_text("🔴 Не удалось расшифровать ГС из-за технического сбоя узла.")
