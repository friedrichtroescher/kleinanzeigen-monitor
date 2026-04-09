# Kleinanzeigen Monitor

Crawls Kleinanzeigen searches, evaluates listings via AI through OpenRouter, and sends matches via Telegram.

## How it works

```
Kleinanzeigen URL → parse HTML → AI evaluates → Telegram message
```

On each run the script iterates over all configured `[[searches]]`. For each search, current listings are scraped from Kleinanzeigen. Every listing not yet in `seen.json` is sent to a language model via [OpenRouter](https://openrouter.ai). The model evaluates based on `profile`, `max_price`, and `prompt` whether the listing is a match. On `match: true` a Telegram message is sent.

**Deduplication**: All seen listing IDs are stored in `seen.json`. Each listing is therefore only evaluated once, regardless of how often the script runs.

**Scheduling**: `setup.sh` registers cron jobs that run at the times configured in `config.toml`.

**Cost**: The script deliberately uses cheap models (e.g. Gemini Flash Lite). With ~50 new listings per day, costs are in the cent range.

## Setup

### 1. Create a Telegram bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name and username (username must end in `bot`, e.g. `my_monitor_bot`)
4. Copy the displayed **bot token** (`123456789:AAF...`)

Get your chat ID:
1. Send a message to the new bot
2. Open in browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Copy `"chat":{"id":...}` from the response

### 2. Get API keys

- **OpenRouter**: Create an account at [openrouter.ai](https://openrouter.ai) → API Keys → create key

### 3. Fill in `.env`

```
cp .env.example .env
```

```
OPENROUTER_API_KEY=sk-or-v1-...
TELEGRAM_BOT_TOKEN=123456789:AAF...
TELEGRAM_CHAT_ID=987654321
```

### 4. Configure searches

Edit `config.toml` — one `[[searches]]` block per search:

```toml
[assistant]
profile = "I'm looking for used items in good condition at fair prices."

[[searches]]
name = "road-bike"
url = "https://www.kleinanzeigen.de/s-rennrad/k0"
max_price = 800
prompt = "Frame 54-56cm, at least Shimano 105, no rust"
```

Just copy the `url` from your browser after searching on Kleinanzeigen.

### 5. Install and test

```bash
./setup.sh
uv run main.py --test-telegram   # Send a test message via Telegram
uv run main.py                   # Single run
crontab -l                       # Check cron jobs
```

### 6. Add `monitor` to your PATH (optional)

Add the project directory to your PATH to use `monitor` as a global command:

```bash
echo 'export PATH="$HOME/path/to/kleinanzeigen-monitor:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then run from anywhere:

```bash
monitor                          # Normal run
monitor --dry-run                # Test without sending notifications
monitor search list              # List configured searches
monitor search add "https://www.kleinanzeigen.de/s-foo/k0" --prompt "..."
```
