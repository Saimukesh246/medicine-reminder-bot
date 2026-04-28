"""
Scheduler for Medicine Reminder Bot.
Handles sending reminders at scheduled times and alerting family on missed doses.
"""

import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

# How long to wait before marking a dose as missed and alerting family
MISSED_DOSE_TIMEOUT_MINUTES = 30


def setup_scheduler(bot: Bot):
    """Initialize the scheduler and attach the bot instance."""
    scheduler.bot = bot

    # Run every minute to check which reminders need to go out
    scheduler.add_job(
        check_and_send_reminders,
        CronTrigger(minute="*", timezone="Asia/Kolkata"),
        id="reminder_checker",
        replace_existing=True,
    )

    # Run every 5 minutes to check for missed doses
    scheduler.add_job(
        check_missed_doses,
        CronTrigger(minute="*/5", timezone="Asia/Kolkata"),
        id="missed_dose_checker",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started.")


async def check_and_send_reminders():
    """Check all active medicines and send reminders at the right times."""
    bot: Bot = scheduler.bot
    now = datetime.now()
    current_time = now.strftime("%H:%M")

    import aiosqlite
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM medicines WHERE active = 1"
        ) as cur:
            medicines = await cur.fetchall()

    for med in medicines:
        times = med["times"].split(",")
        if current_time in times:
            # Check if we already sent a reminder for this time today
            existing = await _already_reminded_today(med["id"], current_time)
            if existing:
                continue

            dose_log_id = await db.log_dose_reminder(med["id"], current_time)

            dosage_text = f" ({med['dosage']})" if med["dosage"] else ""
            notes_text = f"\n📝 {med['notes']}" if med["notes"] else ""

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Taken", callback_data=f"taken:{dose_log_id}"),
                    InlineKeyboardButton("⏰ Snooze 10m", callback_data=f"snooze:{dose_log_id}:{med['id']}"),
                ],
                [
                    InlineKeyboardButton("❌ Skip", callback_data=f"skip:{dose_log_id}"),
                ],
            ])

            try:
                await bot.send_message(
                    chat_id=med["user_id"],
                    text=(
                        f"💊 *Medicine Reminder*\n\n"
                        f"Time to take: *{med['name']}*{dosage_text}\n"
                        f"Scheduled: {current_time}{notes_text}\n\n"
                        f"Please confirm once you've taken it."
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
                logger.info(f"Reminder sent: {med['name']} to user {med['user_id']}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {med['user_id']}: {e}")


async def _already_reminded_today(medicine_id: int, scheduled_time: str) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    import aiosqlite
    async with aiosqlite.connect(db.DB_PATH) as conn:
        async with conn.execute(
            """SELECT COUNT(*) FROM dose_logs
               WHERE medicine_id = ? AND scheduled_time = ? AND date(created_at) = ?""",
            (medicine_id, scheduled_time, today),
        ) as cur:
            row = await cur.fetchone()
            return row[0] > 0


async def check_missed_doses():
    """Check for unacknowledged reminders and alert family members."""
    bot: Bot = scheduler.bot
    cutoff = datetime.now() - timedelta(minutes=MISSED_DOSE_TIMEOUT_MINUTES)

    import aiosqlite
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            """SELECT dl.*, m.name as medicine_name, m.dosage, m.user_id
               FROM dose_logs dl
               JOIN medicines m ON dl.medicine_id = m.id
               WHERE dl.status = 'pending' AND dl.reminded_at < ?""",
            (cutoff.isoformat(),),
        ) as cur:
            overdue = await cur.fetchall()

    for dose in overdue:
        # Mark as missed
        await db.mark_dose_missed(dose["id"])

        # Notify the patient
        try:
            await bot.send_message(
                chat_id=dose["user_id"],
                text=f"⚠️ *Missed Dose*\n\nYou didn't confirm taking *{dose['medicine_name']}* "
                     f"scheduled at {dose['scheduled_time']}.\n\n"
                     f"If you took it late, that's okay! Stay on track for the next one.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to notify patient {dose['user_id']}: {e}")

        # Alert family members
        family = await db.get_family_members(dose["user_id"])
        patient = await db.get_user(dose["user_id"])
        patient_name = patient["full_name"] if patient else "Your family member"

        for member in family:
            try:
                await bot.send_message(
                    chat_id=member["family_user_id"],
                    text=(
                        f"🔔 *Family Alert*\n\n"
                        f"{patient_name} missed their dose of "
                        f"*{dose['medicine_name']}* scheduled at {dose['scheduled_time']}.\n\n"
                        f"You might want to check in with them."
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to alert family member {member['family_user_id']}: {e}")

        logger.info(f"Dose marked missed: {dose['medicine_name']} for user {dose['user_id']}")
