#!/usr/bin/env bash
# Jednorazowe pobranie ogłoszeń z OLX (filtry → AI → listings.json).
# Uruchamiaj z crona co 3 godziny lub ręcznie: ./scripts/collect_listings.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DISABLE_FILE="$ROOT/.collect_listings.disabled"
if [ -f "$DISABLE_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] collect_listings.sh is disabled via $DISABLE_FILE. Exiting."
  exit 0
fi

LOG="$ROOT/cron.log"
LOCK="$ROOT/.collect_listings.lock"

exec >>"$LOG" 2>&1

echo "────────────────────────────────────────────────────────────"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Start collect_listings.sh (pid $$)"

if ! command -v flock >/dev/null 2>&1; then
  echo "Brak flock – uruchamiam bez blokady."
  /usr/bin/python3 "$ROOT/bot.py"
else
  # Uruchom bota z blokadą
  flock -n "$LOCK" /usr/bin/python3 "$ROOT/bot.py"
fi

# Po zakończeniu bota - commit zmian do GitHub (jeśli skonfigurowane)
if [ -f "$ROOT/.env" ] && grep -q "GITHUB_TOKEN=" "$ROOT/.env" && grep -q "GITHUB_REPO=" "$ROOT/.env"; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committing changes to GitHub..."
  
  # Załaduj zmienne środowiskowe
  export $(grep -v '^#' "$ROOT/.env" | xargs)
  
  if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    # Konfiguruj git
    git config user.name "OLX Bot"
    git config user.email "bot@olxbot.local"
    
    # Dodaj zmiany
    git add listings.json seen_ids.json 2>/dev/null || true
    
    # Sprawdź czy są zmiany
    if git diff --cached --quiet; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] No changes to commit."
    else
      # Commit
      git commit -m "Update listings $(date '+%Y-%m-%d %H:%M:%S')" || true
      
      # Push z użyciem tokena
      git push https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git main || \
      git push https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git master || \
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Failed to push to GitHub"
      
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Successfully pushed to GitHub."
    fi
  fi
fi
