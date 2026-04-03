#!/bin/bash
# Kleinanzeigen Monitor Setup – run once

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV=/opt/homebrew/bin/uv

echo "==> Installing dependencies with uv..."
cd "$SCRIPT_DIR"
$UV sync

echo "==> Initializing seen.json..."
if [ ! -f "$SCRIPT_DIR/seen.json" ]; then
    echo "[]" > "$SCRIPT_DIR/seen.json"
fi

echo "==> Installing cron jobs from config.toml..."
$UV run monitor.py --install-cron

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in .env: nano $SCRIPT_DIR/.env"
echo "     OPENROUTER_API_KEY=sk-or-v1-..."
echo "     TELEGRAM_BOT_TOKEN=..."
echo "     TELEGRAM_CHAT_ID=..."
echo ""
echo "  2. Configure searches in config.toml"
echo ""
echo "  3. Test: cd $SCRIPT_DIR && $UV run monitor.py --test"
echo "  4. Check cron: crontab -l"
