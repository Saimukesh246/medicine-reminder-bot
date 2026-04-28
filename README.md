# 💊 Medicine Reminder Bot

A Telegram bot that helps you and your family never miss a medicine dose. Built with Python, it sends timely reminders, tracks dose acknowledgments, and alerts family members when a dose is missed.

## Features

- **Scheduled Reminders** — Set multiple daily reminders per medicine (e.g., 08:00, 14:00, 21:00)
- **One-Tap Confirmation** — Inline buttons to mark doses as Taken, Snoozed, or Skipped
- **Snooze** — 10-minute snooze if you're not ready yet
- **Missed Dose Alerts** — If unacknowledged for 30 minutes, the dose is marked missed
- **Family Alerts** — Linked family members get notified when a dose is missed
- **Daily Tracker** — `/today` shows a live view of all doses and their status
- **Multi-Medicine Support** — Track as many medicines as needed with dosage and notes
- **Lightweight Storage** — SQLite database, zero external dependencies for storage

## Architecture

```
bot.py          → Telegram handlers (commands, conversations, callbacks)
database.py     → SQLite async data layer (users, medicines, logs, family)
scheduler.py    → APScheduler jobs (send reminders, detect missed doses)
```

## Setup

### 1. Create Your Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Install & Configure

```bash
git clone <your-repo-url>
cd medicine-reminder-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and paste your BOT_TOKEN
```

### 3. Run

```bash
python bot.py
```

The bot will:
- Initialize the SQLite database
- Start the reminder scheduler
- Begin polling for Telegram messages

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and see welcome message |
| `/add` | Add a new medicine (guided flow) |
| `/mymeds` | List all active medicines |
| `/today` | See today's dose status |
| `/remove` | Remove a medicine |
| `/addfamily` | Link a family member for alerts |
| `/myfamily` | See linked family members |
| `/removefamily <id>` | Unlink a family member |
| `/help` | Show all commands |

## How It Works

1. **User adds a medicine** via `/add` → stored in SQLite with name, dosage, times, notes
2. **Scheduler runs every minute** → checks if any medicine's scheduled time matches current time
3. **Reminder sent** with inline buttons → user taps ✅ Taken, ⏰ Snooze, or ❌ Skip
4. **If no response in 30 min** → dose marked as missed, family members notified
5. **Daily tracker** via `/today` → shows all doses with ✅/❌/⏳ status

## Deployment

### Option A: Run on a VPS (Recommended)

```bash
# On your server (DigitalOcean, AWS EC2, etc.)
# Use systemd or tmux/screen to keep it running

# systemd service example:
sudo nano /etc/systemd/system/medbot.service
```

```ini
[Unit]
Description=Medicine Reminder Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/medicine-reminder-bot
ExecStart=/home/ubuntu/medicine-reminder-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable medbot
sudo systemctl start medbot
```

### Option B: Railway / Render

Both support Python apps with a `Procfile`:

```
worker: python bot.py
```

## Customization

- **Missed dose timeout** — Change `MISSED_DOSE_TIMEOUT_MINUTES` in `scheduler.py` (default: 30 min)
- **Timezone** — Default is `Asia/Kolkata`, change in `scheduler.py` CronTrigger
- **Snooze duration** — Change the `timedelta(minutes=10)` in `bot.py` button_callback

## Tech Stack

- **python-telegram-bot** — Async Telegram Bot API wrapper
- **APScheduler** — Background job scheduling
- **aiosqlite** — Async SQLite for zero-config storage
- **python-dotenv** — Environment variable management

## License

MIT
