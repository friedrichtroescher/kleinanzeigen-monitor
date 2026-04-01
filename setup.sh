#!/bin/bash
# Kleinanzeigen Monitor Setup – einmalig ausfuehren

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV=/opt/homebrew/bin/uv

echo "==> Installiere Dependencies mit uv..."
cd "$SCRIPT_DIR"
$UV sync

echo "==> Initialisiere seen.json..."
if [ ! -f "$SCRIPT_DIR/seen.json" ]; then
    echo "[]" > "$SCRIPT_DIR/seen.json"
fi

echo "==> Installiere Cron-Jobs aus config.toml..."
$UV run monitor.py --install-cron

echo ""
echo "==> Setup abgeschlossen!"
echo ""
echo "Naechste Schritte:"
echo "  1. .env befuellen: nano $SCRIPT_DIR/.env"
echo "     OPENROUTER_API_KEY=sk-or-v1-..."
echo "     TELEGRAM_BOT_TOKEN=..."
echo "     TELEGRAM_CHAT_ID=..."
echo ""
echo "  2. Suchen in config.toml konfigurieren"
echo ""
echo "  3. Test: cd $SCRIPT_DIR && $UV run monitor.py --test"
echo "  4. Cron pruefen: crontab -l"
