import re
import io
import requests

def translate_to_burmalda(text):
    """Переводит обычный русский текст на язык Бурмалда по твоим правилам"""
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
    """Распознает голосовые сообщения (ГС) через модель Whisper"""
    try:
        API_URL = "https://huggingface.co"
        headers = {"Authorization": f"Bearer {hf_token}"}
        response = requests.post(API_URL, headers=headers, data=audio_bytes)
        return response.json().get("text", "")
    except:
        return ""

def generate_flux_image(prompt, client):
    """Генерирует качественные фото через топовую модель FLUX.1-schnell"""
    try:
        image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")
        bio = io.BytesIO()
        bio.name = 'image.jpeg'
        image.save(bio, 'JPEG')
        bio.seek(0)
        return bio
    except:
        return None
