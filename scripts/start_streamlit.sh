#!/usr/bin/env bash
# Dashboard Streamlit – czyta listings.json zaktualizowany przez bota/cron.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

exec streamlit run app.py --server.headless true --server.port 8502
