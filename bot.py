#!/usr/bin/env python3
"""
OLX Bot – monitor mieszkań na wynajem w Warszawie.
Co 20 minut sprawdza OLX i zapisuje nowe oferty lokalnie do listings.json.

Filtry:
  - Tylko wybrane dzielnice (config.ALLOWED_DISTRICTS)
  - Łączna cena (czynsz najmu + czynsz administracyjny) ≤ config max_total_price
"""

import json
import logging
import re
import time
from pathlib import Path

import requests
import config

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Persistence ────────────────────────────────────────────────────────────
SEEN_IDS_FILE  = Path("seen_ids.json")
LISTINGS_FILE  = Path("listings.json")


def load_seen_ids() -> set:
    if SEEN_IDS_FILE.exists():
        try:
            return set(json.loads(SEEN_IDS_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def save_seen_ids(ids: set) -> None:
    SEEN_IDS_FILE.write_text(json.dumps(list(ids)), encoding="utf-8")


def load_listings() -> dict:
    """Wczytuje zapisane ogłoszenia jako dict {id: record}."""
    if LISTINGS_FILE.exists():
        try:
            return json.loads(LISTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


REPAIR_AI_ERROR_REGEX = re.compile(r"\b429\b|\bToo Many Requests\b", re.IGNORECASE)


def repair_ai_analysis() -> int:
    """Ponawia analizę AI dla zapisanych ogłoszeń z błędem 429 i aktualizuje zapisy."""
    records = load_listings()
    if not records:
        return 0

    try:
        from ai_analyzer import analyze_listing_with_ai
    except ImportError:
        log.error("Nie można załadować modułu ai_analyzer do naprawy AI.")
        return 0

    repaired = 0
    for listing_id, record in records.items():
        ai_notes = str(record.get("ai_analysis", {}).get("ai_notes", ""))
        if not ai_notes:
            continue
        if not REPAIR_AI_ERROR_REGEX.search(ai_notes):
            continue

        title = record.get("title", "")
        description = record.get("description", "")
        rent_price = float(record.get("rent_price", 0) or 0)
        admin_rent = float(record.get("admin_rent", 0) or 0)

        log.info("Naprawiam AI dla ogłoszenia %s (błąd 429).", listing_id)
        ai_res = analyze_listing_with_ai(title, description, rent_price, admin_rent)
        if ai_res and ai_res != record.get("ai_analysis"):
            record["ai_analysis"] = ai_res
            repaired += 1
            LISTINGS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            from ai_analyzer import AI_REPAIR_DELAY_SECONDS
            time.sleep(AI_REPAIR_DELAY_SECONDS)
        except ImportError:
            time.sleep(3)

    return repaired


def save_listing(listing_id: str, listing: dict, meta: dict) -> None:
    """
    Dodaje lub aktualizuje rekord ogłoszenia w listings.json.
    meta = dodatkowe pola obliczone przez bota (dzielnica, ceny łączne, itp.)
    """
    records = load_listings()
    if listing_id not in records:
        from ai_analyzer import analyze_listing_with_ai

        title = listing.get("title", "")
        description = listing.get("description", "")
        rent_price = meta.get("rent_price", 0)
        admin_rent = meta.get("admin_rent", 0)

        ai_res = analyze_listing_with_ai(title, description, rent_price, admin_rent)

        record = {
            "id": listing_id,
            "title": title,
            "url": listing.get("url", ""),
            "description": description,
            "created_time": listing.get("created_time", ""),
            "last_refresh_time": listing.get("last_refresh_time", ""),
            "location": listing.get("location", {}),
            "photos": listing.get("photos", []),
            "params": listing.get("params", []),
            "contact": listing.get("contact", {}),
            "user": listing.get("user", {}),
            "map": listing.get("map", {}),
            # Meta obliczone przez bota
            "district_name": meta.get("district_name", ""),
            "rent_price": rent_price,
            "admin_rent": admin_rent,
            "total_price": meta.get("total_price", 0),
            "found_at": meta.get("found_at", ""),
            # Analiza AI
            "ai_analysis": ai_res,
            # Status oceny przez użytkownika
            "status": "new",  # new | liked | disliked
            "notes": "",
        }
        records[listing_id] = record
        LISTINGS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── API ─────────────────────────────────────────────────────────────────────
OLX_GRAPHQL_URL = "https://www.olx.pl/apigateway/graphql"

GRAPHQL_QUERY = """
query ListingSearchQuery(
  $searchParameters: [SearchParameter!] = []
  $fetchPayAndShip: Boolean = false
  $searchOptions: SearchOptions
) {
  clientCompatibleListings(searchParameters: $searchParameters, searchOptions: $searchOptions) {
    __typename
    ... on ListingSuccess {
      __typename
      data {
        _nodeId
        id
        location {
          city { id name normalized_name _nodeId }
          district { id name normalized_name _nodeId }
          region { id name normalized_name _nodeId }
        }
        last_refresh_time
        created_time
        category { id type _nodeId }
        contact { courier chat name negotiation phone }
        business
        photos { link height rotation width }
        promotion {
          highlighted top_ad options premium_ad_page urgent
          b2c_ad_page seller_badge_x_years_with_olx
        }
        protect_phone
        title
        status
        url
        user {
          id uuid _nodeId about b2c_business_page
          company_name created is_online last_seen
          name other_ads_enabled photo seller_type
          social_network_account_type
          verification { status }
        }
        offer_type
        params {
          key
          name
          type
          value {
            __typename
            ... on GenericParam { key label }
            ... on CheckboxesParam { label checkboxParamKey: key }
            ... on PriceParam {
              value type negotiable label currency
              converted_value converted_currency arranged budget
            }
          }
        }
        description
        external_url
        map { lat lon radius show_detailed zoom }
        safedeal { allowed_quantity weight_grams }
        valid_to_time
        isGpsrAvailable
        payAndShip @include(if: $fetchPayAndShip) {
          sellerPaidDeliveryEnabled
        }
      }
    }
    ... on ListingError {
      __typename
      error { code detail status title }
    }
  }
}
"""


def _build_headers() -> dict:
    """Buduje nagłówki HTTP – dołącza Bearer token jeśli jest dostępny."""
    bearer = config.OLX_BEARER_TOKEN
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        "Origin": "https://www.olx.pl",
        "Referer": "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/",
        "x-client": "DESKTOP",
        "accept-language": "pl",
    }
    if bearer:
        headers["authorization"] = f"Bearer {bearer}"
    return headers


def _build_search_params(offset: int, search_cfg: dict) -> list[dict]:
    """Buduje listę searchParameters dla zapytania GraphQL (mieszkania)."""
    params = [
        {"key": "offset",      "value": str(offset)},
        {"key": "limit",       "value": str(config.PAGE_SIZE)},
        {"key": "category_id", "value": search_cfg["category_id"]},
        {"key": "region_id",   "value": search_cfg["region_id"]},
        {"key": "city_id",     "value": search_cfg["city_id"]},
        {"key": "owner_type",  "value": search_cfg["owner_type"]},
    ]

    # Filtry pięter
    for i, floor in enumerate(search_cfg.get("floor_select", [])):
        params.append({"key": f"filter_enum_floor_select[{i}]", "value": floor})

    # Filtry liczby pokoi
    for i, room in enumerate(search_cfg.get("rooms", [])):
        params.append({"key": f"filter_enum_rooms[{i}]", "value": room})

    # Cena
    params.append({"key": "filter_float_price:from", "value": search_cfg["price_from"]})
    params.append({"key": "filter_float_price:to",   "value": search_cfg["price_to"]})

    params.append({"key": "suggest_filters", "value": "true"})
    params.append({"key": "sl", "value": "19d5884e8b4x9f2399e1"})

    return params


def _fetch_page(offset: int, search_cfg: dict) -> list[dict]:
    """Pobiera jedną stronę wyników z OLX (offset = numer pierwszego rekordu)."""
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {
            "searchParameters": _build_search_params(offset, search_cfg),
            "fetchPayAndShip": False,
            "searchOptions": None,
        },
    }
    try:
        resp = requests.post(OLX_GRAPHQL_URL, json=payload, headers=_build_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            log.error("GraphQL errors: %s", data["errors"])
            return []
        page = (
            data.get("data", {})
                .get("clientCompatibleListings", {})
                .get("data") or []
        )
        return page
    except requests.RequestException as exc:
        log.error("Błąd połączenia z OLX (offset=%d): %s", offset, exc)
        return []
    except (KeyError, TypeError, ValueError) as exc:
        log.error("Błąd parsowania odpowiedzi OLX (offset=%d): %s", offset, exc)
        return []


def fetch_listings(search_cfg: dict) -> list[dict]:
    """Pobiera WSZYSTKIE ogłoszenia z OLX dla danego wyszukiwania (paginacja)."""
    all_listings: list[dict] = []
    seen_on_page: set = set()

    for page_num in range(config.MAX_PAGES):
        offset = page_num * config.PAGE_SIZE
        log.info("[%s] Strona %d/%d (offset=%d)…",
                 search_cfg["name"], page_num + 1, config.MAX_PAGES, offset)

        page = _fetch_page(offset, search_cfg)

        if not page:
            log.info("Brak wyników na stronie %d – koniec paginacji.", page_num + 1)
            break

        new_on_page = [l for l in page if l.get("id") not in seen_on_page]
        for l in new_on_page:
            seen_on_page.add(l["id"])
        all_listings.extend(new_on_page)

        if len(page) < config.PAGE_SIZE:
            log.info("Ostatnia strona (tylko %d wyników). Koniec paginacji.", len(page))
            break

        time.sleep(0.5)

    log.info("[%s] Pobrano %d ogłoszeń.", search_cfg["name"], len(all_listings))
    return all_listings


# ─── Filtering ───────────────────────────────────────────────────────────────

def get_param_value(listing: dict, key: str):
    """Zwraca wartość parametru wg klucza lub None."""
    for param in listing.get("params", []):
        if param.get("key") == key:
            return param.get("value", {})
    return None


def get_rent_price(listing: dict) -> float:
    """Zwraca cenę najmu (price) jako liczbę."""
    val = get_param_value(listing, "price")
    if val and isinstance(val.get("value"), (int, float)):
        return float(val["value"])
    return 0.0


def get_admin_rent(listing: dict) -> float:
    """Zwraca czynsz administracyjny (rent) jako liczbę, lub 0 jeśli brak."""
    val = get_param_value(listing, "rent")
    if val:
        # GenericParam ma klucz "key" z wartością numeryczną jako string
        raw = val.get("key", "")
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    return 0.0


def get_district_id(listing: dict) -> int | None:
    """Zwraca ID dzielnicy ogłoszenia lub None."""
    district = listing.get("location", {}).get("district")
    if district and isinstance(district.get("id"), int):
        return district["id"]
    return None


def is_allowed_district(listing: dict) -> bool:
    """Sprawdza czy ogłoszenie pochodzi z dozwolonej dzielnicy."""
    district_id = get_district_id(listing)
    if district_id is None:
        # Brak informacji o dzielnicy – pomijamy
        log.debug("Ogłoszenie %s bez dzielnicy – pomijam.", listing.get("id"))
        return False
    return district_id in config.ALLOWED_DISTRICTS


def is_total_price_ok(listing: dict, max_total: float) -> bool:
    """Sprawdza czy łączna cena (czynsz + rent) nie przekracza limitu."""
    rent_price = get_rent_price(listing)
    admin_rent = get_admin_rent(listing)
    total = rent_price + admin_rent
    return total <= max_total


def matches_keywords(title: str, description: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    clean_desc = re.sub(r"<[^>]+>", " ", description or "")
    text = (title + " " + clean_desc).lower()
    for kw in keywords:
        if not re.search(kw, text, re.IGNORECASE):
            return False
    return True


def matches_excluded_keywords(title: str, description: str, excluded_keywords: list[str]) -> bool:
    if not excluded_keywords:
        return False
    clean_desc = re.sub(r"<[^>]+>", " ", description or "")
    text = (title + " " + clean_desc).lower()
    for kw in excluded_keywords:
        if re.search(kw, text, re.IGNORECASE):
            return True
    return False


# ─── Formatting ──────────────────────────────────────────────────────────────

def get_thumbnail(listing: dict) -> str | None:
    """Zwraca URL miniatury pierwszego zdjęcia."""
    photos = listing.get("photos", [])
    if photos:
        link = photos[0].get("link", "")
        return link.replace("{width}", "400").replace("{height}", "300")
    return None


def format_message(listing: dict, search_name: str) -> tuple[str, str]:
    """
    Zwraca (short_msg, full_msg) dla Telegrama.
    short_msg – caption pod zdjęciem (do ~1024 znaków).
    full_msg  – pełny komunikat z opisem.
    """
    title = listing.get("title", "Brak tytułu")
    url   = listing.get("url", "")

    # Lokalizacja
    loc_data  = listing.get("location", {})
    city      = loc_data.get("city", {}).get("name", "Warszawa")
    district  = loc_data.get("district", {}).get("name", "")
    loc_str   = f"{city}, {district}" if district else city

    seller = listing.get("user", {}).get("name", "")

    # Ceny
    rent_price = get_rent_price(listing)
    admin_rent = get_admin_rent(listing)
    total      = rent_price + admin_rent

    price_label = get_param_value(listing, "price") or {}
    price_str   = price_label.get("label", f"{rent_price:.0f} zł") if isinstance(price_label, dict) else str(rent_price)

    rent_str  = f"{admin_rent:.0f} zł" if admin_rent else "—"
    total_str = f"{total:.0f} zł"

    # Parametry mieszkania
    def param_label(key: str) -> str:
        val = get_param_value(listing, key)
        if val and isinstance(val, dict):
            return val.get("label", "—")
        return "—"

    area      = param_label("m")
    rooms     = param_label("rooms")
    floor     = param_label("floor_select")
    furniture = param_label("furniture")
    elevator  = param_label("winda")
    pets      = param_label("pets")
    builttype = param_label("builttype")

    # Kontakt
    contact = listing.get("contact", {})
    contact_parts = []
    if contact.get("phone"):       contact_parts.append("📞 telefon")
    if contact.get("chat"):        contact_parts.append("💬 czat OLX")
    if contact.get("negotiation"): contact_parts.append("🤝 negocjacje")
    contact_str = " | ".join(contact_parts) if contact_parts else "—"

    # Data dodania
    created = listing.get("created_time", "")
    if created:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(created)
            created_str = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            created_str = created[:10]
    else:
        created_str = "—"

    # Opis – usuń HTML, skróć
    raw_desc = listing.get("description") or ""
    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
    if len(clean_desc) > 600:
        clean_desc = clean_desc[:600].rsplit(" ", 1)[0] + "…"
    if not clean_desc:
        clean_desc = "(brak opisu)"

    # ── Krótka wersja (caption pod zdjęciem) ─────────────────────────────
    short_msg = (
        f"🏠 <b>Nowe mieszkanie!</b>\n"
        f"\n"
        f"<b>{title}</b>\n"
        f"📍 {loc_str}\n"
        f"\n"
        f"💰 <b>Czynsz najmu:</b> {price_str}\n"
        f"🏢 <b>Czynsz admin.:</b> {rent_str}\n"
        f"💵 <b>Łącznie:</b> {total_str}\n"
        f"\n"
        f"📐 {area}  🛏 {rooms}  🏗 piętro {floor}\n"
        f"🪑 Umeblowane: {furniture}  🛗 Winda: {elevator}\n"
        f"\n"
        f"👤 {seller}\n"
        f"🔗 <a href=\"{url}\">Otwórz ogłoszenie</a>"
    )

    # ── Pełna wersja z opisem ─────────────────────────────────────────────
    full_msg = (
        f"🏠 <b>[{search_name}] Szczegóły ogłoszenia:</b>\n"
        f"\n"
        f"<b>{title}</b>\n"
        f"📍 <b>Lokalizacja:</b> {loc_str}\n"
        f"\n"
        f"💰 <b>Czynsz najmu:</b> {price_str}\n"
        f"🏢 <b>Czynsz admin.:</b> {rent_str}\n"
        f"💵 <b>Łącznie:</b> <b>{total_str}</b>\n"
        f"\n"
        f"📐 <b>Powierzchnia:</b> {area}\n"
        f"🛏 <b>Pokoje:</b> {rooms}\n"
        f"🏗 <b>Piętro:</b> {floor}\n"
        f"🪑 <b>Umeblowane:</b> {furniture}\n"
        f"🛗 <b>Winda:</b> {elevator}\n"
        f"🐾 <b>Zwierzęta:</b> {pets}\n"
        f"🏢 <b>Zabudowa:</b> {builttype}\n"
        f"\n"
        f"👤 <b>Właściciel:</b> {seller}\n"
        f"📅 <b>Data dodania:</b> {created_str}\n"
        f"📬 <b>Kontakt:</b> {contact_str}\n"
        f"\n"
        f"📝 <b>Opis:</b>\n"
        f"{clean_desc}\n"
        f"\n"
        f"🔗 <a href=\"{url}\">{url}</a>"
    )

    return short_msg, full_msg


# ─── Telegram ────────────────────────────────────────────────────────────────

# ─── Main Check ──────────────────────────────────────────────────────────────

def run_check() -> None:
    """Główna funkcja: pobiera oferty, filtruje po dzielnicy i łącznej cenie, zgłasza nowe."""
    log.info("═" * 60)
    log.info("Sprawdzam OLX dla wszystkich wyszukiwań…")

    seen_ids = load_seen_ids()
    new_count_total = 0

    fixed = repair_ai_analysis()
    if fixed:
        log.info("Naprawiono analizę AI dla %d zapisanych ogłoszeń z błędem 429.", fixed)

    for search_cfg in config.SEARCHES:
        log.info("🔍 Przeszukuję: %s…", search_cfg["name"])
        listings = fetch_listings(search_cfg)
        new_count_this_search = 0
        max_total = search_cfg.get("max_total_price", float("inf"))

        for listing in listings:
            listing_id = str(listing.get("id", ""))
            if not listing_id:
                continue

            if listing_id in seen_ids:
                continue

            title       = listing.get("title", "")
            description = listing.get("description", "")

            # ── Filtr 1: Dzielnica ─────────────────────────────────────────
            district_id   = get_district_id(listing)
            district_name = config.ALLOWED_DISTRICTS.get(district_id, "—") if district_id else "—"
            if not is_allowed_district(listing):
                log.debug("⛔ Pomijam (dzielnica %s/%s): %s", district_id, district_name, title)
                seen_ids.add(listing_id)  # zapamiętaj żeby nie przetwarzać ponownie
                continue

            # ── Filtr 2: Łączna cena ──────────────────────────────────────
            rent_price = get_rent_price(listing)
            admin_rent = get_admin_rent(listing)
            total      = rent_price + admin_rent
            if not is_total_price_ok(listing, max_total):
                log.info(
                    "⛔ Pomijam (cena łączna %.0f zł > max %.0f zł): %s",
                    total, max_total, title,
                )
                seen_ids.add(listing_id)
                continue

            # ── Filtr 3: Słowa kluczowe ───────────────────────────────────
            if not matches_keywords(title, description, search_cfg.get("required_keywords", [])):
                seen_ids.add(listing_id)
                continue

            if matches_excluded_keywords(title, description, search_cfg.get("excluded_keywords", [])):
                seen_ids.add(listing_id)
                continue

            # ── Nowe pasujące ogłoszenie! ──────────────────────────────────
            log.info(
                "✅ Nowe: [%s] %s | czynsz: %.0f + admin: %.0f = łącznie: %.0f zł",
                district_name, title, rent_price, admin_rent, total,
            )

            # Zapisz pełne dane ogłoszenia do listings.json
            from datetime import datetime, timezone
            save_listing(listing_id, listing, {
                "district_name": district_name,
                "rent_price": rent_price,
                "admin_rent": admin_rent,
                "total_price": total,
                "found_at": datetime.now(timezone.utc).isoformat(),
            })

            seen_ids.add(listing_id)
            new_count_this_search += 1
            new_count_total += 1

        if new_count_this_search == 0:
            log.info("[%s] Brak nowych ofert.", search_cfg["name"])
        else:
            log.info("[%s] Znaleziono %d nowych ofert.", search_cfg["name"], new_count_this_search)

    save_seen_ids(seen_ids)

    if new_count_total == 0:
        log.info("Łącznie: brak nowych pasujących ogłoszeń.")
    else:
        log.info("Łącznie: znaleziono i zgłoszono %d nowych ogłoszeń.", new_count_total)

    log.info("Następne sprawdzenie za %d minut.", config.CHECK_INTERVAL_MINUTES)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("🤖 OLX Bot (Mieszkania) uruchomiony!")
    log.info(
        "Liczba wyszukiwań: %d | Co %d min | Dozwolone dzielnice: %s",
        len(config.SEARCHES),
        config.CHECK_INTERVAL_MINUTES,
        ", ".join(config.ALLOWED_DISTRICTS.values()),
    )

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning(
            "⚠️  UWAGA: Brak konfiguracji Telegrama!\n"
            "Skopiuj .env.example → .env i uzupełnij TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID."
        )

    run_check()