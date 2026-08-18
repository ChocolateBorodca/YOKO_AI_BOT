async def handle_ai_logic(user_id, user_text, current_mode):
    if current_mode == "mellstroy":
        prompt = "Ты — Меллстрой, хайповый стример. Говори дерзко, используй сленг: боров, легенда, хайп, суета, крутим слоты. Отвечай кратко, в 1-2 предложениях."
    else:
        prompt = "Ты — вежливый и полезный ИИ ассистент по имени YOKO. Отвечай дружелюбно, грамотно и коротко."

    try:
        # ЗАПРОС НАПРЯМУЮ К СЕРВЕРАМ HUGGING FACE ЧЕРЕЗ ТВОЙ ТОКЕН
        hf_token = os.getenv("HF_TOKEN")
        
        # Используем мощную модель Llama-3 от Meta
        API_URL = "https://huggingface.co"
        headers = {"Authorization": f"Bearer {hf_token}"}
        
        # Формируем правильный формат диалога для ИИ
        payload = {
            "inputs": f"<|system|>\n{prompt}\n<|user|>\n{user_text}\n<|assistant|>\n",
            "parameters": {"max_new_tokens": 150, "return_full_text": False}
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            # Получаем чистый текст ответа
            res_json = response.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                answer = res_json[0].get("generated_text", "").strip()
            else:
                answer = res_json.get("generated_text", "").strip()
        else:
            answer = f"🔴 Ошибка узла ИИ Hugging Face (Код {response.status_code})"
            
    except Exception as e:
        answer = f"🔴 Сбой связи с Hugging Face: {str(e)[:40]}"

    if not answer:
        answer = "ИИ-сервер обрабатывает поток данных, повтори запрос!"

    if current_mode == "mellstroy" and "🔴" not in answer: 
        answer = translate_to_burmalda(answer)
    return answer
