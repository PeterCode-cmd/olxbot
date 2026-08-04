# OLX Bot – Monitor mieszkań na wynajem w Warszawie

Bot co **20 minut** sprawdza OLX w poszukiwaniu mieszkań na wynajem w Warszawie. Filtruje po dzielnicach i cenie, analizuje oferty z AI i wysyła powiadomienia na **Telegram**. Posiada również dashboard Streamlit do przeglądania ofert.

## Wymagania

- Python 3.10+
- Konto i bot na Telegram

## Instalacja

```bash
# Sklonuj/wejdź do katalogu projektu
cd olxbot

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj przykładowy plik konfiguracyjny
cp .env.example .env

# Uzupełnij .env swoimi danymi (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY)
# Dla Streamlit Cloud dodaj również: GITHUB_TOKEN, GITHUB_REPO
```

## Konfiguracja Telegrama

1. Otwórz Telegram i napisz do **@BotFather**
2. Wyślij `/newbot` i postępuj zgodnie z instrukcjami → dostaniesz **BOT_TOKEN**
3. Wyślij dowolną wiadomość do swojego bota
4. Wejdź na `https://api.telegram.org/bot<TWOJ_TOKEN>/getUpdates` → skopiuj `"id"` z pola `"chat"` – to Twój **CHAT_ID**
5. Uzupełnij plik `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwXyz
TELEGRAM_CHAT_ID=123456789
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Konfiguracja Groq AI (opcjonalne)

Bot używa Groq AI do analizy ogłoszeń. Aby skonfigurować:

1. Zarejestruj się na [console.groq.com](https://console.groq.com)
2. Utwórz API key
3. Dodaj do `.env`:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Uruchomienie

### Bot (cron)

```bash
python bot.py
```

Bot od razu wykona pierwsze sprawdzenie, a następnie co określony czas (domyślnie 20 minut) automatycznie sprawdza nowe ogłoszenia.

### Dashboard Streamlit (lokalnie)

```bash
streamlit run app.py
```

Dashboard będzie dostępny na `http://localhost:8501`

### Dashboard Streamlit (jako service)

```bash
# Włącz systemd service
sudo systemctl enable olxbot-streamlit.service
sudo systemctl start olxbot-streamlit.service

# Sprawdź status
sudo systemctl status olxbot-streamlit.service
```

Dashboard będzie dostępny na `http://localhost:8502`

### Uruchomienie w cronie

Bot jest skonfigurowany do automatycznego działania w cronie co godzinę:

```cron
0 * * * * /bin/bash /home/piotrmalec/AntigravityProjects/olxbot/scripts/collect_listings.sh
```

Aby zmienić interwał, edytuj crontab (`crontab -e`) i zmień pierwsze pole:
- `0 * * * *` = co godzinę (o każdej pełnej godzinie)
- `*/30 * * * *` = co 30 minut
- `0 */3 * * *` = co 3 godziny

## Deployment na Streamlit Cloud (opcja hybrydowa)

### Konfiguracja GitHub

1. **Utwórz Personal Access Token:**
   - Wejdź na GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Kliknij "Generate new token (classic)"
   - Nadaj nazwę (np. "olxbot-streamlit")
   - Wybierz uprawnienia: `repo` (full control)
   - Skopiuj wygenerowany token

2. **Dodaj token do `.env`:**
```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=username/olxbot
```
   - Zamień `username/olxbot` na nazwę Twojego repozytorium GitHub

3. **Zainicjuj git repo (jeśli jeszcze nie masz):**
```bash
cd /home/piotrmalec/AntigravityProjects/olxbot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/olxbot.git
git push -u origin main
```

### Konfiguracja Streamlit Cloud

1. **Wgraj projekt na GitHub:**
   - Upewnij się że wszystkie pliki są w repozytorium GitHub
   - `listings.json` powinien być w repo (będzie aktualizowany przez crona)

2. **Utwórz aplikację na Streamlit Cloud:**
   - Wejdź na [share.streamlit.io](https://share.streamlit.io)
   - Kliknij "New app"
   - Wybierz swoje repozytorium i plik `app.py`
   - Kliknij "Deploy"

3. **Dodaj sekrety w Streamlit Cloud:**
   - W ustawieniach aplikacji → Secrets
   - Dodaj:
     ```
     GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
     GITHUB_REPO=username/olxbot
     ```

### Jak to działa

- **Lokalnie:** Cron uruchamia `collect_listings.sh` → bot aktualizuje `listings.json` → skrypt commituje zmiany do GitHub
- **Streamlit Cloud:** Aplikacja pobiera `listings.json` z GitHub API → wyświetla dane → zmiany (status, notatki) są zapisywane z powrotem do GitHub

### Uwagi

- Upewnij się że `listings.json` nie jest w `.gitignore`
- Token GitHub powinien mieć uprawnienia `repo`
- Zmiany w Streamlit Cloud są synchronizowane z GitHub w czasie rzeczywistym

## Personalizacja

Edytuj `config.py` aby zmienić:

| Parametr | Domyślna wartość | Opis |
|---|---|---|
| `ALLOWED_DISTRICTS` | Mokotów, Wola, Ochota, Śródmieście, Bemowo, Wilanów, Żoliborz, Bielany, Włochy, Ursus | Dozwolone dzielnice |
| `CHECK_INTERVAL_MINUTES` | 20 | Jak często bot sprawdza OLX |
| `MAX_TOTAL_PRICE` | 3400 | Maksymalna łączna cena (czynsz + admin) |
| `SEARCHES` | 2-pok i 1-pok w Warszawie | Konfiguracja wyszukiwań |

## Pliki

| Plik | Opis |
|---|---|
| `bot.py` | Główna logika bota |
| `app.py` | Dashboard Streamlit |
| `config.py` | Konfiguracja |
| `.env` | Klucze API (nie commituj!) |
| `listings.json` | Baza danych ogłoszeń (synchronizowana z GitHub) |
| `seen_ids.json` | Zapamiętane ID ogłoszeń (auto-tworzy się) |
| `bot.log` | Logi działania bota |
| `cron.log` | Logi działania crona |
