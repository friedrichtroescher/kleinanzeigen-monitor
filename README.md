# Kleinanzeigen Monitor

Crawlt Kleinanzeigen-Suchanfragen, bewertet Inserate per KI über OpenRouter und schickt Treffer via Telegram.

## Funktionsweise

```
Kleinanzeigen-URL → HTML parsen → KI bewertet → Telegram-Nachricht
```

Bei jedem Lauf iteriert das Skript über alle konfigurierten `[[searches]]`. Pro Suche werden die aktuellen Inserate von Kleinanzeigen gescrapt. Jedes Inserat, das noch nicht in `seen.json` steht, wird an ein Sprachmodell via [OpenRouter](https://openrouter.ai) geschickt. Das Modell bewertet anhand von `profile`, `max_price` und `prompt` ob das Inserat ein Treffer ist. Bei `match: true` geht eine Telegram-Nachricht raus.

**Deduplizierung**: Alle gesehenen Inserat-IDs werden in `seen.json` gespeichert. Jedes Inserat wird also nur einmal bewertet, egal wie oft das Skript läuft.

**Scheduling**: `setup.sh` trägt Cron-Jobs ein, die zu den in `config.toml` konfigurierten Uhrzeiten laufen.

**Kosten**: Das Skript nutzt bewusst günstige Modelle (z.B. Gemini Flash Lite). Bei ~50 neuen Inseraten pro Tag liegen die Kosten im Cent-Bereich.

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
prompt = "Rahmen 54-56cm, mind. Shimano 105, kein Rost"
```

Die `url` einfach aus dem Browser kopieren, nachdem man auf Kleinanzeigen gesucht hat.

### 5. Installieren und testen

```bash
./setup.sh
uv run monitor.py --test   # Testnachricht via Telegram
uv run monitor.py          # Einmaliger Lauf
crontab -l                 # Cron-Jobs prüfen
```
