FROM python:3.12-slim

WORKDIR /app

# зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# сам скрипт
COPY news_to_telegram.py .

CMD ["python", "news_to_telegram.py"]

