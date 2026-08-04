import os
from dotenv import load_dotenv

load_dotenv()

# ─── OLX Auth ──────────────────────────────────────────────────────────────
# Bearer token z zalogowanej sesji (wygasa co ~15 min – wtedy trzeba zaktualizować)
OLX_BEARER_TOKEN = os.getenv("OLX_BEARER_TOKEN", "")

# ─── Telegram / powiadomienia ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── GitHub (dla Streamlit Cloud) ─────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

# ─── AI rate limits ─────────────────────────────────────────────────────────
AI_MAX_REQUESTS_PER_MINUTE = 30
AI_MAX_REQUESTS_PER_DAY = 1000
AI_MIN_SECONDS_BETWEEN_CALLS = 3

# ─── District whitelist (Warszawa) ──────────────────────────────────────────
# Tylko te dzielnice chcemy widzieć. Mapowanie ID → nazwa dla logów.
ALLOWED_DISTRICTS = {
    353: "Mokotów",
    359: "Wola",
    355: "Ochota",
    351: "Śródmieście",
    367: "Bemowo",
    375: "Wilanów",
    363: "Żoliborz",
    369: "Bielany",
    357: "Włochy",
    371: "Ursus"
}

# ─── OLX Search Parameters ──────────────────────────────────────────────────
# Jedno wyszukiwanie = mieszkania 2-pokojowe na wynajem w Warszawie,
# wyłącznie od właścicieli, piętra 1-11, cena ogłoszenia 2000–3400 zł.
# Łączna cena (czynsz + rent) nie może przekroczyć MAX_TOTAL_PRICE.
SEARCHES = [
    {
        "name": "Mieszkania 2-pok Warszawa wynajem",
        "category_id": "15",         # Wynajem mieszkań
        "region_id": "2",            # Mazowieckie
        "city_id": "17871",          # Warszawa
        "owner_type": "private",
        "price_from": "2000",
        "price_to": "3400",
        "rooms": ["two"],
        "floor_select": [
            "floor_1", "floor_10", "floor_11", "floor_2", "floor_3",
            "floor_4", "floor_5", "floor_6", "floor_7", "floor_8", "floor_9",
        ],
        "max_total_price": 3400,
        "required_keywords": [],
        "excluded_keywords": [],
    },
    {
        "name": "Mieszkania 1-pok Warszawa wynajem",
        "category_id": "15",         # Wynajem mieszkań
        "region_id": "2",            # Mazowieckie
        "city_id": "17871",          # Warszawa
        "owner_type": "private",
        "price_from": "2000",
        "price_to": "3400",
        "rooms": ["one"],
        "floor_select": [
            "floor_1", "floor_10", "floor_11", "floor_2", "floor_3",
            "floor_4", "floor_5", "floor_6", "floor_7", "floor_8", "floor_9",
        ],
        "max_total_price": 3400,
        "required_keywords": [],
        "excluded_keywords": [],
    },
]

# Paginacja
PAGE_SIZE = 40
MAX_PAGES = 10

# ─── Scheduler ──────────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 20
