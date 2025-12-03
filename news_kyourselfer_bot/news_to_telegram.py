import os
import requests
import datetime as dt
import logging
from googletrans import Translator

# === Планировщик ===
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ===== НАСТРОЙКИ =====

# Ключи и chat_id берём из переменных окружения
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # например: -1001234567890

# Компании, по которым собираем новости
COMPANIES = ["NVIDIA", "Tesla", "SpaceX"]
ARTICLES_PER_COMPANY = 3

# Время и таймзона для ежедневного запуска
RUN_AT = os.getenv("RUN_AT", "22:05")                # формат HH:MM
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow") # IANA, например Europe/Moscow
RUN_ON_START = os.getenv("RUN_ON_START", "true").lower() in {"1", "true", "yes", "y"}

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# Инициализируем переводчик один раз
translator = Translator()

# Проверяем, что всё нужное передано
if not all([NEWS_API_KEY, TELEGRAM_TOKEN, CHAT_ID]):
    raise RuntimeError("Нужно задать переменные окружения: NEWS_API_KEY, TELEGRAM_TOKEN, CHAT_ID")


def translate_to_ru(text: str) -> str:
    """
    Перевод текста на русский через googletrans.
    При ошибке возвращаем оригинал.
    """
    if not text:
        return ""
    try:
        result = translator.translate(text, dest="ru")
        return result.text
    except Exception as e:
        logging.warning(f"Ошибка перевода: {e}")
        return text


def get_top_news(company: str):
    """
    Получение топ-новостей по компании через NewsAPI (https://newsapi.org).
    Берём англоязычные новости и переводим их сами.
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": company,
        "language": "en",          # источник — англоязычные новости
        "sortBy": "publishedAt",   # можно поменять на popularity/relevancy
        "pageSize": ARTICLES_PER_COMPANY,
        "apiKey": NEWS_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("articles", [])


def build_message() -> str:
    """
    Собираем один текстовый дайджест для отправки в Telegram.
    """
    today = dt.date.today().strftime("%d.%m.%Y")
    parts = [f"Топ-новости за {today} по NVIDIA, Tesla, SpaceX (перевод на русский):"]

    for company in COMPANIES:
        parts.append(f"\n<b>{company}</b>")
        articles = get_top_news(company)
        if not articles:
            parts.append("— новостей не найдено.")
            continue

        for i, a in enumerate(articles, start=1):
            title_en = a.get("title", "Без заголовка")
            desc_en = a.get("description", "")
            url = a.get("url", "")
            source = a.get("source", {}).get("name", "Источник")

            # Переводим заголовок и описание
            title_ru = translate_to_ru(title_en)
            desc_ru = translate_to_ru(desc_en) if desc_en else ""

            block_lines = [f"{i}. {title_ru} ({source})"]
            if desc_ru:
                block_lines.append(desc_ru)
            if url:
                block_lines.append(url)

            parts.append("\n".join(block_lines))

    return "\n".join(parts)


def send_to_telegram(text: str):
    """
    Отправка готового текста в Telegram-чат/канал.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()


def run_digest():
    """
    Одна итерация дайджеста: собрать и отправить.
    Оборачиваем в try/except, чтобы планировщик не падал при ошибках.
    """
    try:
        logging.info("Старт формирования дайджеста…")
        msg = build_message()
        send_to_telegram(msg)
        logging.info("Дайджест отправлен в Telegram.")
    except Exception as e:
        logging.exception(f"Сбой при формировании/отправке дайджеста: {e}")


def _parse_hhmm(s: str):
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except Exception:
        raise ValueError("RUN_AT должен быть в формате HH:MM, например '09:30'.")


if __name__ == "__main__":
    hour, minute = _parse_hhmm(RUN_AT)

    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        run_digest,
        CronTrigger(hour=hour, minute=minute),
        id="daily_news_digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,  # если запуск пропущен (сон/рестарт), выполнит один раз после возобновления
    )

    logging.info(f"Ежедневный запуск запланирован на {RUN_AT} ({TIMEZONE}). "
                 f"Измените переменные окружения RUN_AT и TIMEZONE при необходимости.")

    # Разовый прогон сразу при старте (можно отключить RUN_ON_START=false)
    if RUN_ON_START:
        run_digest()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановка планировщика…")

