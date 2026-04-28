# 💊 Medicine Reminder Bot

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![APScheduler](https://img.shields.io/badge/Scheduler-APScheduler-orange)](https://apscheduler.readthedocs.io/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)

> A production-ready Telegram bot that ensures medication adherence through automated reminders, real-time dose tracking, and family alert notifications — built with async Python for reliable, lightweight operation.

---

## 🎯 Problem Statement

Medication non-adherence affects **50% of patients** with chronic conditions, leading to preventable hospitalizations and health complications. Elderly patients and those on complex multi-drug regimens are most at risk — especially when caregivers can't be physically present.

**Medicine Reminder Bot** solves this by combining automated scheduling, one-tap confirmations, and a family alert system into a single zero-cost Telegram bot.

---

## ✨ Key Features

### For Patients
- **Multi-Schedule Reminders** — Configure multiple daily reminder times per medicine (e.g., `08:00, 14:00, 21:00`)
- **One-Tap Response** — Inline keyboard buttons: ✅ Taken · ⏰ Snooze (10 min) · ❌ Skip
- **Daily Dose Tracker** — Real-time status dashboard via `/today` with ✅/❌/⏳ indicators
- **Unlimited Medicines** — Track any number of medicines with dosage, schedule, and custom notes

### For Families & Caregivers
- **Missed Dose Alerts** — Automatic notifications to linked family members after 30 minutes of no response
- **Easy Linking** — Simple `/addfamily` flow using Telegram user IDs
- **Relationship Tagging** — Label each link (Son, Daughter, Spouse, Caretaker, etc.)

### Technical
- **Fully Async** — Built on `python-telegram-bot` async API and `aiosqlite` for non-blocking I/O
- **Zero Infrastructure** — SQLite database, no external services required beyond Telegram
- **Persistent Scheduling** — APScheduler with cron triggers, survives message delays
- **Idempotent Reminders** — Deduplication logic prevents duplicate notifications per time slot

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Telegram API                          │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  bot.py — Command & Callback Router                          │
│                                                              │
│  • ConversationHandler  →  /add, /remove, /addfamily         │
│  • CommandHandler       →  /start, /mymeds, /today, /help    │
│  • CallbackQueryHandler →  Taken / Snooze / Skip buttons     │
└────────┬──────────────────────────────────┬──────────────────┘
         │                                  │
         ▼                                  ▼
┌──────────────────────┐    ┌──────────────────────────────────┐
│  database.py         │    │  scheduler.py                     │
│                      │    │                                   │
│  • Users CRUD        │◄───│  • check_and_send_reminders()     │
│  • Medicines CRUD    │    │    ↳ Runs every minute             │
│  • Dose Logs         │    │  • check_missed_doses()           │
│  • Family Links      │    │    ↳ Runs every 5 minutes          │
│                      │    │  • Snooze re-reminders            │
│  [SQLite + aiosqlite]│    │  [APScheduler AsyncIOScheduler]   │
└──────────────────────┘    └──────────────────────────────────┘
```

### Reminder Lifecycle

```
  /add medicine (name, dosage, times, notes)
         │
         ▼
  Stored in SQLite ──── Scheduler polls every 60s
                                  │
                        Time matches? ──── No ──► Skip
                                  │
                                 Yes
                                  │
                        Already reminded today? ── Yes ──► Skip
                                  │
                                  No
                                  │
                    ┌─────────────▼──────────────┐
                    │   💊 Reminder Sent          │
                    │   [Taken] [Snooze] [Skip]   │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────┼──────────────┐
                    ▼             ▼              ▼
               ✅ Taken     ⏰ Snooze       ❌ Skip
              (log: taken)   (10 min)      (log: missed)
                              │
                         Re-remind
                              │
                    No response after 30 min?
                              │
                    ┌─────────▼─────────┐
                    │  ⚠️ Missed Dose    │
                    │  → Notify patient  │
                    │  → Alert family    │
                    └───────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- A Telegram account
- A bot token from [@BotFather](https://t.me/BotFather)

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/medicine-reminder-bot.git
cd medicine-reminder-bot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and add your BOT_TOKEN
```

### Run

```bash
python bot.py
```

On startup, the bot will:
1. Initialize the SQLite database (creates tables if first run)
2. Start the APScheduler background jobs
3. Begin polling the Telegram Bot API for updates

---

## 📋 Command Reference

| Command | Description | Type |
|---------|-------------|------|
| `/start` | Register user and display welcome message | Instant |
| `/add` | Add a new medicine with guided prompts | Conversation |
| `/mymeds` | List all active medicines with schedules | Instant |
| `/today` | View today's dose tracker (✅/❌/⏳) | Instant |
| `/remove` | Deactivate a medicine reminder | Conversation |
| `/addfamily` | Link a family member for missed-dose alerts | Conversation |
| `/myfamily` | View all linked family members | Instant |
| `/removefamily <id>` | Unlink a family member by user ID | Instant |
| `/help` | Display all available commands | Instant |

---

## 🗄️ Database Schema

```sql
users            — Registered bot users (Telegram ID, name, timezone)
medicines        — Active/inactive medicines (name, dosage, schedule times, notes)
dose_logs        — Per-dose tracking (pending → taken/missed, timestamps)
family_links     — Patient ↔ Family member relationships
```

---

## ☁️ Deployment

### Option A — VPS with systemd (Recommended)

```ini
# /etc/systemd/system/medbot.service

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
Environment=BOT_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable medbot && sudo systemctl start medbot
```

### Option B — Railway / Render

Both platforms support the included `Procfile`. Set `BOT_TOKEN` as an environment variable in the platform dashboard.

```
worker: python bot.py
```

---

## ⚙️ Configuration

| Parameter | File | Default | Description |
|-----------|------|---------|-------------|
| `MISSED_DOSE_TIMEOUT_MINUTES` | `scheduler.py` | `30` | Minutes before marking dose as missed |
| `timezone` | `scheduler.py` | `Asia/Kolkata` | Timezone for all cron triggers |
| Snooze duration | `bot.py` | `10 min` | Delay before snooze re-reminder |
| `DB_PATH` | `database.py` | `medicine_reminder.db` | SQLite database file path |

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Bot Framework | [python-telegram-bot 21.6](https://github.com/python-telegram-bot/python-telegram-bot) | Async Telegram Bot API wrapper |
| Scheduler | [APScheduler 3.10](https://apscheduler.readthedocs.io/) | Cron-based background job scheduling |
| Database | [aiosqlite 0.20](https://github.com/omnilib/aiosqlite) | Async SQLite — zero-config persistence |
| Config | [python-dotenv 1.0](https://github.com/theskumar/python-dotenv) | `.env` file loading |

---

## 🗺️ Roadmap

- [ ] Multi-timezone support per user
- [ ] Weekly/monthly adherence reports with charts
- [ ] Natural language time input ("twice a day", "every 8 hours")
- [ ] WhatsApp integration via Twilio
- [ ] Prescription photo storage
- [ ] Doctor/pharmacy contact quick-dial

---

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for better medication adherence
</p>
