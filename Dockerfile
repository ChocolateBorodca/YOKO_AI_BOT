FROM python:3.9

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app

# ИСПРАВЛЕНО: Инструкции для принудительного проброса ключа из Render в Docker
ARG OPENROUTER_KEY
ENV OPENROUTER_KEY=$OPENROUTER_KEY

COPY --chown=user . /app

RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD ["python", "-u", "main.py"]
