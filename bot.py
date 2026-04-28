"""
Medicine Reminder Bot — Main entry point.

Commands:
    /start          — Register and see welcome message
    /add            — Add a new medicine reminder
    /mymeds         — List all active medicines
    /today          — See today's dose status
    /remove         — Remove a medicine
    /addfamily      — Link a family member for alerts
    /myfamily       — List linked family members
    /removefamily   — Unlink a family member
    /help           — Show all commands
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import database as db
from scheduler import setup_scheduler

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ── Conversation states for /add flow ────────────────────────────
MED_NAME, MED_DOSAGE, MED_TIMES, MED_NOTES = range(4)

# ── Conversation states for /addfamily flow ──────────────────────
FAMILY_ID, FAMILY_RELATION = range(10, 12)

# ── Conversation states for /remove flow ─────────────────────────
REMOVE_PICK = range(20, 21)


# ═══════════════════════════════════════════════════════════════════
#  BASIC COMMANDS
# ═══════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.upsert_user(user.id, user.username or "", user.full_name or "")
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm your *Medicine Reminder Bot*. I'll help you or your family never miss a dose.\n\n"
        f"🔹 /add — Add a medicine reminder\n"
        f"🔹 /mymeds — View your medicines\n"
        f"🔹 /today — Today's dose status\n"
        f"🔹 /addfamily — Link family for missed-dose alerts\n"
        f"🔹 /help — All commands\n\n"
        f"Let's start! Use /add to add your first medicine.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *All Commands*\n\n"
        "/add — Add a new medicine\n"
        "/mymeds — List active medicines\n"
        "/today — Today's dose tracker\n"
        "/remove — Stop a medicine reminder\n"
        "/addfamily — Link a family member\n"
        "/myfamily — See linked family\n"
        "/removefamily — Unlink a family member\n"
        "/help — Show this message",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════════
#  ADD MEDICINE (Conversation)
# ═══════════════════════════════════════════════════════════════════

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💊 *Add a Medicine*\n\nWhat's the medicine name?\n\n(e.g., Paracetamol, Metformin, Vitamin D)",
        parse_mode="Markdown",
    )
    return MED_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["med_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Got it: *{context.user_data['med_name']}*\n\n"
        f"What's the dosage?\n(e.g., 500mg, 1 tablet, 5ml syrup)\n\n"
        f"Send /skip if you don't want to specify.",
        parse_mode="Markdown",
    )
    return MED_DOSAGE


async def add_dosage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["med_dosage"] = "" if text == "/skip" else text
    await update.message.reply_text(
        "⏰ *When should I remind you?*\n\n"
        "Send times in 24hr format, separated by commas.\n\n"
        "Examples:\n"
        "• `08:00` — once daily\n"
        "• `08:00,14:00,21:00` — three times a day\n"
        "• `09:00,21:00` — twice daily",
        parse_mode="Markdown",
    )
    return MED_TIMES


async def add_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    times = [t.strip() for t in raw.split(",")]

    # Validate time format
    import re
    for t in times:
        if not re.match(r"^\d{2}:\d{2}$", t):
            await update.message.reply_text(
                f"❌ `{t}` isn't valid. Use HH:MM format (e.g., 08:00, 14:30).\nTry again:",
                parse_mode="Markdown",
            )
            return MED_TIMES

    context.user_data["med_times"] = times
    await update.message.reply_text(
        "📝 Any special notes?\n(e.g., Take after food, With warm water)\n\nSend /skip if none.",
        parse_mode="Markdown",
    )
    return MED_NOTES


async def add_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    notes = "" if text == "/skip" else text

    user_id = update.effective_user.id
    name = context.user_data["med_name"]
    dosage = context.user_data["med_dosage"]
    times = context.user_data["med_times"]

    med_id = await db.add_medicine(user_id, name, dosage, times, notes)

    times_str = ", ".join(times)
    dosage_str = f"\n💉 Dosage: {dosage}" if dosage else ""
    notes_str = f"\n📝 Notes: {notes}" if notes else ""

    await update.message.reply_text(
        f"✅ *Medicine Added!*\n\n"
        f"💊 {name}{dosage_str}\n"
        f"⏰ Reminders: {times_str}{notes_str}\n\n"
        f"I'll remind you at the scheduled times. Use /mymeds to see all your medicines.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. No medicine was added.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  VIEW MEDICINES
# ═══════════════════════════════════════════════════════════════════

async def my_meds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meds = await db.get_medicines(update.effective_user.id)
    if not meds:
        await update.message.reply_text(
            "You have no active medicines. Use /add to add one!"
        )
        return

    lines = ["💊 *Your Medicines*\n"]
    for med in meds:
        dosage = f" ({med['dosage']})" if med["dosage"] else ""
        times = med["times"].replace(",", ", ")
        notes = f"\n   📝 {med['notes']}" if med["notes"] else ""
        lines.append(f"*{med['id']}.* {med['name']}{dosage}\n   ⏰ {times}{notes}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════
#  TODAY'S STATUS
# ═══════════════════════════════════════════════════════════════════

async def today_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = await db.get_today_logs(update.effective_user.id)
    if not logs:
        await update.message.reply_text(
            "📅 No reminders sent yet today. They'll come at the scheduled times!"
        )
        return

    status_icons = {"taken": "✅", "missed": "❌", "pending": "⏳"}
    lines = ["📅 *Today's Doses*\n"]
    for log in logs:
        icon = status_icons.get(log["status"], "❓")
        dosage = f" ({log['dosage']})" if log["dosage"] else ""
        lines.append(f"{icon} {log['scheduled_time']} — {log['medicine_name']}{dosage} [{log['status']}]")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════
#  REMOVE MEDICINE (Conversation)
# ═══════════════════════════════════════════════════════════════════

async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meds = await db.get_medicines(update.effective_user.id)
    if not meds:
        await update.message.reply_text("You have no active medicines to remove.")
        return ConversationHandler.END

    lines = ["Which medicine do you want to remove? Send the *number*:\n"]
    for med in meds:
        lines.append(f"*{med['id']}.* {med['name']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    return REMOVE_PICK


async def remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        med_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please send a valid number.")
        return REMOVE_PICK

    await db.deactivate_medicine(med_id, update.effective_user.id)
    await update.message.reply_text(f"✅ Medicine #{med_id} has been removed.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════
#  FAMILY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

async def add_family_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍👩‍👧 *Link a Family Member*\n\n"
        "Ask your family member to message this bot first (so I can reach them).\n\n"
        "Then send me their *Telegram user ID*.\n"
        "They can get it by messaging @userinfobot on Telegram.",
        parse_mode="Markdown",
    )
    return FAMILY_ID


async def add_family_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        family_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("That's not a valid user ID. Send a number.")
        return FAMILY_ID

    context.user_data["family_id"] = family_id
    await update.message.reply_text(
        "What's their relationship to you?\n(e.g., Son, Daughter, Spouse, Caretaker)"
    )
    return FAMILY_RELATION


async def add_family_relation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    relation = update.message.text.strip()
    family_id = context.user_data["family_id"]
    user_id = update.effective_user.id

    await db.add_family_link(user_id, family_id, relation)
    await update.message.reply_text(
        f"✅ Family member linked!\n\n"
        f"They'll be alerted if you miss a dose for more than 30 minutes."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def my_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    family = await db.get_family_members(update.effective_user.id)
    if not family:
        await update.message.reply_text(
            "No family members linked. Use /addfamily to add one!"
        )
        return

    lines = ["👨‍👩‍👧 *Linked Family Members*\n"]
    for f in family:
        lines.append(f"• ID: `{f['family_user_id']}` — {f['relationship']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def remove_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick removal: /removefamily <user_id>"""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/removefamily <user_id>`\n\nUse /myfamily to see linked IDs.",
            parse_mode="Markdown",
        )
        return

    try:
        family_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return

    await db.remove_family_link(update.effective_user.id, family_id)
    await update.message.reply_text(f"✅ Family member {family_id} unlinked.")


# ═══════════════════════════════════════════════════════════════════
#  INLINE BUTTON CALLBACKS (Taken / Snooze / Skip)
# ═══════════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("taken:"):
        dose_log_id = int(data.split(":")[1])
        await db.mark_dose_taken(dose_log_id)
        await query.edit_message_text("✅ Great! Dose marked as *taken*. Keep it up! 💪", parse_mode="Markdown")

    elif data.startswith("skip:"):
        dose_log_id = int(data.split(":")[1])
        await db.mark_dose_missed(dose_log_id)
        await query.edit_message_text("⏭️ Dose skipped. Try not to miss the next one!", parse_mode="Markdown")

    elif data.startswith("snooze:"):
        parts = data.split(":")
        dose_log_id = int(parts[1])
        medicine_id = int(parts[2])
        await query.edit_message_text("⏰ Snoozed! I'll remind you again in 10 minutes.", parse_mode="Markdown")

        # Schedule a one-time snooze reminder
        from datetime import datetime, timedelta
        run_time = datetime.now() + timedelta(minutes=10)

        async def snooze_reminder():
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Taken", callback_data=f"taken:{dose_log_id}"),
                    InlineKeyboardButton("❌ Skip", callback_data=f"skip:{dose_log_id}"),
                ],
            ])
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text="⏰ *Snooze Reminder!*\n\nTime to take your medicine now!",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

        from scheduler import scheduler
        scheduler.add_job(snooze_reminder, "date", run_date=run_time)


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found! Set it in .env file.")
        print("   Get one from @BotFather on Telegram.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Register handlers ────────────────────────────────────────

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mymeds", my_meds))
    app.add_handler(CommandHandler("today", today_status))
    app.add_handler(CommandHandler("myfamily", my_family))
    app.add_handler(CommandHandler("removefamily", remove_family))

    # Add medicine conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            MED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            MED_DOSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_dosage),
                CommandHandler("skip", add_dosage),
            ],
            MED_TIMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_times)],
            MED_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_notes),
                CommandHandler("skip", add_notes),
            ],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    ))

    # Remove medicine conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("remove", remove_start)],
        states={
            REMOVE_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_pick)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    ))

    # Add family conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addfamily", add_family_start)],
        states={
            FAMILY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_family_id)],
            FAMILY_RELATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_family_relation)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    ))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(button_callback))

    # ── Initialize DB and scheduler on startup ───────────────────
    async def post_init(application: Application):
        await db.init_db()
        setup_scheduler(application.bot)
        logger.info("Bot is running!")

    app.post_init = post_init

    # ── Start polling ────────────────────────────────────────────
    print("🚀 Medicine Reminder Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
