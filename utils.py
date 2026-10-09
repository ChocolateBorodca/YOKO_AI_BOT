import re
import httpx  # Перешли на асинхронный httpx вместо requests

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

async def transcribe_audio(audio_bytes, hf_token):
    """ИСПРАВЛЕНО: Асинхронный запрос к настоящему Inference API Hugging Face (модель Whisper)"""
    try:
        # Используем быструю и точную модель Whisper-Large-V3-Turbo
        API_URL = "https://huggingface.co"
        headers = {"Authorization": f"Bearer {hf_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, headers=headers, content=audio_bytes, timeout=30.0)
            
        if response.status_code == 200:
            return response.json().get("text", "")
        else:
            print(f"Ошибка Whisper API (Код {response.status_code}): {response.text}")
            return ""
    except Exception as e:
        print(f"Исключение при вызове Whisper API: {e}")
        return ""

async def process_voice_message(update, context, hf_token, handle_ai_logic_func, get_user_data_func):
    user_id = update.message.from_user.id
    is_premium, current_mode = get_user_data_func(user_id)
    
    if not is_premium:
        await update.message.reply_text("❌ Функция работы с ГС доступна только Premium пользователям! Жми /buy ⚡")
        return
        
    await update.message.reply_text("🎙️ Расшифровываю голосовое сообщение, подожди...")
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio = await file.download_as_bytearray()
        
        # ИСПРАВЛЕНО: Теперь вызываем асинхронную функцию через await
        text = await transcribe_audio(bytes(audio), hf_token)
        
        if not text:
            await update.message.reply_text("❌ Не удалось разобрать слова в аудио. Возможно, плохая запись или Hugging Face перегружен.")
            return
            
        answer = await handle_ai_logic_func(user_id, text, current_mode)
        await update.message.reply_text(f"💬 Расшифровка ГС:\n«{text}»\n\n🤖 Ответ ИИ:\n{answer}")
    except Exception as e:
        print(f"Ошибка обработки ГС в боте: {e}")
        await update.message.reply_text("🔴 Не удалось обработать аудиофайл из-за внутренней ошибки.")
