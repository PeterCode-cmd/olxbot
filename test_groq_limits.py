#!/usr/bin/env python3
"""
Skrypt testowy do sprawdzania limitów API Groq.
Pomaga zrozumieć limity tokens/min i jak unikać błędu 429.
"""

import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

def count_tokens(text: str) -> int:
    """Szacuje liczbę tokenów (bardzo przybliżone - ~4 znaki = 1 token)."""
    return len(text) // 4

def test_api_call(title: str, description: str, rent_price: float, admin_rent: float, delay_seconds: int = 0) -> dict:
    """Wykonuje pojedyncze zapytanie do API i zwraca wynik."""
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
        "Authorization": f"Bearer {GROQ_API_KEY}",
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

    # Szacowanie tokenów
    total_text = system_prompt + user_prompt
    estimated_tokens = count_tokens(total_text)

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    start_time = time.time()
    try:
        resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time
        
        if resp.status_code == 429:
            return {
                "success": False,
                "error": "429 Too Many Requests",
                "status_code": 429,
                "estimated_tokens": estimated_tokens,
                "elapsed_seconds": elapsed,
                "delay_before": delay_seconds
            }
        
        resp.raise_for_status()
        data = resp.json()
        
        # Sprawdź nagłówki rate limit jeśli są
        rate_limit_headers = {}
        for key, value in resp.headers.items():
            if 'rate' in key.lower() or 'limit' in key.lower() or 'remaining' in key.lower():
                rate_limit_headers[key] = value
        
        return {
            "success": True,
            "status_code": resp.status_code,
            "estimated_tokens": estimated_tokens,
            "elapsed_seconds": elapsed,
            "delay_before": delay_seconds,
            "rate_limit_headers": rate_limit_headers
        }
        
    except requests.RequestException as exc:
        return {
            "success": False,
            "error": str(exc),
            "estimated_tokens": estimated_tokens,
            "elapsed_seconds": elapsed,
            "delay_before": delay_seconds
        }

def main():
    if not GROQ_API_KEY:
        print("❌ Brak GROQ_API_KEY w .env")
        return

    print("🧪 Testowanie limitów API Groq")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"API Key: {GROQ_API_KEY[:20]}...")
    print()

    # Dane testowe
    short_title = "Mieszkanie testowe"
    short_description = "Krótki opis mieszkania do testów."
    short_rent = 2000.0
    short_admin = 500.0

    long_title = "Wynajmę mieszkanie 2-pokojowe w Warszawie na Mokotowie"
    long_description = """
    Wynajmę mieszkanie 2-pokojowe w Warszawie na Mokotowie. Mieszkanie jest w pełni umeblowane 
    i wyposażone. Znajduje się na 3 piętrze w budynku z windą. Powierzchnia mieszkania to 45 m². 
    Składa się z dwóch oddzielnych pokoi, kuchni, łazienki oraz balkonu. Kuchnia jest w pełni 
    wyposażona w lodówkę, kuchenkę elektryczną, zmywarkę i mikrofalę. W łazience znajduje się prysznic, 
    umywalka i WC. Mieszkanie jest po generalnym remoncie - nowe podłogi, okna, instalacje. 
    Czynsz najmu wynosi 2800 zł miesięcznie, dodatkowo czynsz administracyjny to około 500 zł. 
    W czynsz administracyjny wliczone są ogrzewanie, woda, ścieki. Prąd i gaz płatne według zużycia. 
    Kaucja jednomiesięczna. Preferowany najem długoterminowy. Mieszkanie dostępne od 1 września. 
    Blisko stacja metra Wilanowska, liczne sklepy i restauracje w okolicy. Kontakt telefoniczny 
    pod numer 123-456-789. Możliwość oglądania w godzinach wieczornych po wcześniejszym uzgodnieniu.
    """ * 3  # Powtórz 3 razy dla symulacji ~1000 tokens
    long_rent = 2800.0
    long_admin = 500.0

    # Test 1: Krótkie zapytania bez opóźnienia
    print("📋 Test 1: 5 krótkich zapytań bez opóźnienia (powinno wywołać 429)")
    print("-" * 60)
    for i in range(5):
        result = test_api_call(short_title, short_description, short_rent, short_admin, delay_seconds=0)
        status = "✅" if result["success"] else "❌"
        print(f"{status} Zapytanie {i+1}: {result['estimated_tokens']} tokens, "
              f"{result['elapsed_seconds']:.2f}s, delay: {result['delay_before']}s")
        if not result["success"]:
            print(f"   Błąd: {result.get('error', 'Unknown')}")
            if result.get("rate_limit_headers"):
                print(f"   Rate limit headers: {result['rate_limit_headers']}")
        time.sleep(1)  # Mała przerwa między testami
    
    print()
    print("⏱️  Czekam 10 sekund przed kolejnym testem...")
    time.sleep(10)
    print()

    # Test 2: Zapytania z opóźnieniem 10 sekund
    print("📋 Test 2: 3 zapytania z opóźnieniem 10 sekund")
    print("-" * 60)
    for i in range(3):
        result = test_api_call(short_title, short_description, short_rent, short_admin, delay_seconds=10)
        status = "✅" if result["success"] else "❌"
        print(f"{status} Zapytanie {i+1}: {result['estimated_tokens']} tokens, "
              f"{result['elapsed_seconds']:.2f}s, delay: {result['delay_before']}s")
        if not result["success"]:
            print(f"   Błąd: {result.get('error', 'Unknown')}")
    
    print()
    print("⏱️  Czekam 15 sekund przed kolejnym testem...")
    time.sleep(15)
    print()

    # Test 3: Długie zapytania (symulacja opisów z OLX)
    print("📋 Test 3: 3 długie zapytania (~1000 tokens) z opóźnieniem 10 sekund")
    print("-" * 60)
    for i in range(3):
        result = test_api_call(long_title, long_description, long_rent, long_admin, delay_seconds=10)
        status = "✅" if result["success"] else "❌"
        print(f"{status} Zapytanie {i+1}: {result['estimated_tokens']} tokens, "
              f"{result['elapsed_seconds']:.2f}s, delay: {result['delay_before']}s")
        if not result["success"]:
            print(f"   Błąd: {result.get('error', 'Unknown')}")
            if result.get("rate_limit_headers"):
                print(f"   Rate limit headers: {result['rate_limit_headers']}")
    
    print()
    print("=" * 60)
    print("✅ Testy zakończone")
    print()
    print("📊 Wnioski:")
    print("- Jeśli test 1 wywołał 429, to limit jest bardzo restrykcyjny")
    print("- Jeśli test 2 przeszedł, to 10 sekund opóźnienia może być wystarczające")
    print("- Test 3 pokazuje jak długie zapytania (~1000 tokens) wpływają na limity")
    print("- Sprawdź nagłówki rate_limit aby poznać dokładne limity")

if __name__ == "__main__":
    main()
