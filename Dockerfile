# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# сначала только зависимости — лучше кешируется
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# потом весь код
COPY . .

# если у них основной скрипт другой — подставь своё имя
CMD ["python", "./proxy/tg_ws_proxy.py", "--host", "0.0.0.0", "--port", "1080", "--dc-ip", "1:149.154.175.205", "--dc-ip", "2:149.154.167.220"]
