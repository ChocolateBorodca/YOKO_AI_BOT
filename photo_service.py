import io

def generate_flux_image(prompt, client):
    """
    Генерирует качественные фото через модель FLUX.1-schnell.
    Принимает текстовый запрос (prompt) и ИИ-клиент Hugging Face.
    Возвращает готовый буфер с картинкой для отправки в Telegram.
    """
    try:
        # Обращаемся к топовой бесплатной модели FLUX на серверах Hugging Face
        image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")
        
        # Сохраняем полученное изображение в буфер оперативной памяти
        bio = io.BytesIO()
        bio.name = 'image.jpeg'
        image.save(bio, 'JPEG')
        bio.seek(0)
        
        return bio
    except Exception as e:
        print(f"Ошибка генерации картинки: {e}")
        return None
