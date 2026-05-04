FROM python:3.9
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"
WORKDIR /app
COPY --chown=user . /app
RUN pip install --no-cache-dir --upgrade -r requirements.txt
CMD ["python", "-u", "main.py"]
