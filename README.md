# Kleinanzeigen Monitor

Crawlt Kleinanzeigen-Suchanfragen stündlich, bewertet neue Inserate per KI und schickt Treffer via Telegram.

## Setup

### 1. Telegram-Bot erstellen

1. [@BotFather](https://t.me/BotFather) auf Telegram öffnen
2. `/newbot` senden
3. Name und Username vergeben (Username muss auf `bot` enden, z.B. `mein_monitor_bot`)
4. Den angezeigten **Bot-Token** kopieren (`123456789:AAF...`)

Chat-ID ermitteln:
1. Eine Nachricht an den neuen Bot schicken
2. Im Browser öffnen: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. `"chat":{"id":...}` aus der Antwort kopieren

### 2. API-Keys holen

- **OpenRouter**: Account auf [openrouter.ai](https://openrouter.ai) → API Keys → Key erstellen

### 3. `.env` befüllen

```
cp .env.example .env
```

```
OPENROUTER_API_KEY=sk-or-v1-...
TELEGRAM_BOT_TOKEN=123456789:AAF...
TELEGRAM_CHAT_ID=987654321
```

### 4. Suchen konfigurieren

`config.toml` anpassen – pro Suche ein `[[searches]]`-Block:

```toml
[assistant]
profile = "Ich suche gebrauchte Gegenstände in gutem Zustand zu fairen Preisen."

[[searches]]
name = "rennrad"
url = "https://www.kleinanzeigen.de/s-rennrad/k0"
max_price = 800
criteria = "Rahmen 54-56cm, mind. Shimano 105, kein Rost"
```

Die `url` einfach aus dem Browser kopieren, nachdem man auf Kleinanzeigen gesucht hat.

### 5. Installieren und testen

```bash
./setup.sh
uv run monitor.py --test   # Testnachricht via Telegram
uv run monitor.py          # Einmaliger Lauf
crontab -l                 # Cron-Jobs prüfen
```
