import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"

AI_USAGE_FILE = Path(__file__).parent / "ai_usage.json"
AI_MAX_REQUESTS_PER_MINUTE = int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", "6"))  # 6000 tokens/min / ~1000 tokens per request
AI_MAX_REQUESTS_PER_DAY = int(os.getenv("AI_MAX_REQUESTS_PER_DAY", "1000"))
AI_MIN_SECONDS_BETWEEN_CALLS = int(os.getenv("AI_MIN_SECONDS_BETWEEN_CALLS", "10"))  # 10 seconds between calls
AI_REPAIR_DELAY_SECONDS = int(os.getenv("AI_REPAIR_DELAY_SECONDS", "10"))
AI_RETRY_BACKOFF = [5, 10, 15]


def _load_ai_usage() -> dict:
    today = date.today().isoformat()
    if AI_USAGE_FILE.exists():
        try:
            state = json.loads(AI_USAGE_FILE.read_text(encoding="utf-8"))
            if state.get("date") != today:
                return {"date": today, "count": 0, "calls": [], "last_call_ts": 0.0}
            state.setdefault("calls", [])
            state.setdefault("count", 0)
            state.setdefault("last_call_ts", 0.0)
            return state
        except (json.JSONDecodeError, ValueError):
            pass
    return {"date": today, "count": 0, "calls": [], "last_call_ts": 0.0}


def _save_ai_usage(state: dict) -> None:
    AI_USAGE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _throttle_ai_request() -> bool:
    state = _load_ai_usage()
    now = time.time()

    # reset hourly/minute window by pruning old calls and dropping stale date
    calls = [ts for ts in state.get("calls", []) if now - ts < 60]
    state["calls"] = calls

    if len(calls) >= AI_MAX_REQUESTS_PER_MINUTE:
        oldest = min(calls)
        sleep_time = max(0.0, 60 - (now - oldest))
        log.warning("Osiągnięto limit %d zapytań AI na minutę. Czekam %.1f sekundy.", AI_MAX_REQUESTS_PER_MINUTE, sleep_time)
        time.sleep(sleep_time)
        now = time.time()
        calls = [ts for ts in state["calls"] if now - ts < 60]

    if state["count"] >= AI_MAX_REQUESTS_PER_DAY:
        log.warning("Osiągnięto dzienny limit AI (%d zapytań). Pomijam zapytanie.", AI_MAX_REQUESTS_PER_DAY)
        return False

    elapsed = now - state.get("last_call_ts", 0.0)
    if elapsed < AI_MIN_SECONDS_BETWEEN_CALLS:
        wait = AI_MIN_SECONDS_BETWEEN_CALLS - elapsed
        log.debug("Oczekiwanie %0.1f sekundy między zapytaniami AI.", wait)
        time.sleep(wait)
        now = time.time()

    state["calls"].append(now)
    state["count"] += 1
    state["last_call_ts"] = now
    _save_ai_usage(state)
    return True


def _fallback_ai_result(rent_price: float, admin_rent: float, error: str) -> dict:
    return {
        "ai_total_price": rent_price + admin_rent + 200.0,
        "ai_notes": f"Używam szacunkowej wartości, ponieważ analiza AI nie powiodła się: {error}",
        "media_cost": 200.0,
        "deposit": "Nieznana",
        "lease_type": "Nieznany",
    }


def analyze_listing_with_ai(title: str, description: str, rent_price: float, admin_rent: float) -> dict:
    """
    Analizuje opis mieszkania za pomocą modelu Groq (llama-3.3-70b-versatile).
    Zwraca słownik:
    {
        "ai_total_price": float,
        "ai_notes": str,
        "media_cost": float,
        "deposit": str,
        "lease_type": str
    }
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        log.warning("Brak GROQ_API_KEY w .env – pomijam analizę AI.")
        return {
            "ai_total_price": rent_price + admin_rent + 200.0,
            "ai_notes": "Brak klucza GROQ_API_KEY w pliku .env.",
            "media_cost": 200.0,
            "deposit": "Nieznana",
            "lease_type": "Nieznany",
        }

    system_prompt = (
        "Jesteś precyzyjnym asystentem analizującym ogłoszenia wynajmu mieszkań w Polsce. "
        "Twoim zadaniem jest przeczytanie opisu mieszkania i obliczenie faktycznej, całkowitej miesięcznej kwoty najmu. "
        "Domyślnie koszty mediów (prąd, gaz, woda, ogrzewanie) wynoszą 200 zł miesięcznie, CHYBA że w opisie wyraźnie podano inne kwoty lub podano że media są w cenie. "
        "Zwróć odpowiedź WYŁĄCZNIE jako czysty obiekt JSON w podanym formacie, bez żadnego dodatkowego tekstu ani formatowania markdown."
    )

    user_prompt = f"""
Tytuł ogłoszenia: {title}
Czynsz najmu (odstępne podane w ogłoszeniu): {rent_price} zł
Czynsz administracyjny: {admin_rent} zł

Opis ogłoszenia:
{description}

Wymagany format odpowiedzi JSON:
{{
    "ai_total_price": (liczba float: suma = czynsz najmu + czynsz admin + wyliczone/szacowane media + inne obowiązkowe opłaty),
    "media_cost": (liczba float: szacowane lub podane w opisie media/opłaty. Jeśli brak w opisie, przyjmij 200.0),
    "deposit": (string: kwota kaucji jeśli podana, np. "4000 zł" lub "Brak info"),
    "lease_type": (string: "najem okazjonalny" / "zwykły" / "Brak info"),
    "ai_notes": (string: krótkie zwięzłe podsumowanie po polsku, skąd taka kwota, co zawiera, czy garaż jest w cenie, kaucja itp.)
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    if not _throttle_ai_request():
        return _fallback_ai_result(rent_price, admin_rent, "limit dzienny lub minutowy")

    for attempt, backoff in enumerate([0] + AI_RETRY_BACKOFF, start=1):
        if backoff > 0:
            log.info("Ponawiam zapytanie AI po %d sekundach (próba %d).", backoff, attempt)
            time.sleep(backoff)

        try:
            resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=20)
            if resp.status_code == 429:
                log.warning("Groq AI zwrócił 429 Too Many Requests. Próba %d/%d.", attempt, len(AI_RETRY_BACKOFF) + 1)
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return {
                "ai_total_price": float(result.get("ai_total_price", rent_price + admin_rent + 200.0)),
                "ai_notes": str(result.get("ai_notes", "")),
                "media_cost": float(result.get("media_cost", 200.0)),
                "deposit": str(result.get("deposit", "Nieznana")),
                "lease_type": str(result.get("lease_type", "Nieznany")),
            }
        except requests.RequestException as exc:
            log.warning("Błąd połączenia z Groq AI: %s", exc)
            if attempt == len(AI_RETRY_BACKOFF) + 1:
                return _fallback_ai_result(rent_price, admin_rent, str(exc))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            log.error("Błąd dekodowania odpowiedzi Groq AI: %s", exc)
            return _fallback_ai_result(rent_price, admin_rent, str(exc))

    return _fallback_ai_result(rent_price, admin_rent, "nie udało się uzyskać odpowiedzi AI")
