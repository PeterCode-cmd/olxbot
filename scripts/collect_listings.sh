#!/usr/bin/env bash
# Single OLX listing fetch (filters -> AI -> listings.json).
# Run from cron every 10 min or manually: ./scripts/collect_listings.sh

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

echo "------------------------------------------------------------"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Start collect_listings.sh (pid $$)"

if ! command -v flock >/dev/null 2>&1; then
  echo "No flock - running without lock."
  /usr/bin/python3 "$ROOT/bot.py"
else
  # Run bot with lock
  if flock -n "$LOCK" /usr/bin/python3 "$ROOT/bot.py"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot finished successfully."
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot already running (lock held). Skipping this run."
    exit 0
  fi
fi

# After bot finishes - commit changes to GitHub (if configured)
if [ -f "$ROOT/.env" ] && grep -q "GITHUB_TOKEN=" "$ROOT/.env" && grep -q "GITHUB_REPO=" "$ROOT/.env"; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committing changes to GitHub..."
  
  # Load environment variables
  export $(grep -v '^#' "$ROOT/.env" | xargs)
  
  if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    # Configure git
    git config user.name "OLX Bot"
    git config user.email "bot@olxbot.local"
    
    # Add changes
    git add listings.json seen_ids.json 2>/dev/null || true
    
    # Check if there are changes
    if git diff --cached --quiet; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] No changes to commit."
    else
      # Commit
      git commit -m "Update listings $(date '+%Y-%m-%d %H:%M:%S')" || true
      
      # Stash any uncommitted changes (in case of local edits)
      git stash push -m "Auto-stash before pull" 2>/dev/null || true
      
      # Pull remote changes first (in case Streamlit Cloud made changes)
      git pull --rebase https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git main 2>/dev/null || \
      git pull --rebase https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git master 2>/dev/null || \
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pull failed or no remote"
      
      # Unstash if we stashed
      git stash pop 2>/dev/null || true
      
      # Push with token
      git push https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git main || \
      git push https://"$GITHUB_TOKEN"@github.com/"$GITHUB_REPO".git master || \
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Failed to push to GitHub"
      
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] Successfully pushed to GitHub."
    fi
  fi
fi
