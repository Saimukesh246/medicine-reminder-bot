"""
Database layer for Medicine Reminder Bot.
Uses SQLite for lightweight, zero-config storage.
"""

import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "medicine_reminder.db")


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                timezone TEXT DEFAULT 'Asia/Kolkata',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                dosage TEXT,
                times TEXT NOT NULL,  -- comma-separated HH:MM times, e.g. "08:00,14:00,21:00"
                notes TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS dose_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',  -- pending, taken, missed
                reminded_at TIMESTAMP,
                responded_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id)
            );

            CREATE TABLE IF NOT EXISTS family_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_user_id INTEGER NOT NULL,
                family_user_id INTEGER NOT NULL,
                relationship TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_user_id) REFERENCES users(user_id),
                FOREIGN KEY (family_user_id) REFERENCES users(user_id),
                UNIQUE(patient_user_id, family_user_id)
            );
        """)
        await db.commit()


# ── User Operations ──────────────────────────────────────────────

async def upsert_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username=?, full_name=?""",
            (user_id, username, full_name, username, full_name),
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


# ── Medicine Operations ──────────────────────────────────────────

async def add_medicine(user_id: int, name: str, dosage: str, times: list[str], notes: str = ""):
    times_str = ",".join(times)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO medicines (user_id, name, dosage, times, notes) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, dosage, times_str, notes),
        )
        await db.commit()
        return cursor.lastrowid


async def get_medicines(user_id: int, active_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM medicines WHERE user_id = ?"
        if active_only:
            query += " AND active = 1"
        async with db.execute(query, (user_id,)) as cur:
            return await cur.fetchall()


async def deactivate_medicine(medicine_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE medicines SET active = 0 WHERE id = ? AND user_id = ?",
            (medicine_id, user_id),
        )
        await db.commit()


# ── Dose Log Operations ─────────────────────────────────────────

async def log_dose_reminder(medicine_id: int, scheduled_time: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO dose_logs (medicine_id, scheduled_time, status, reminded_at) VALUES (?, ?, 'pending', ?)",
            (medicine_id, scheduled_time, datetime.now().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def mark_dose_taken(dose_log_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dose_logs SET status = 'taken', responded_at = ? WHERE id = ?",
            (datetime.now().isoformat(), dose_log_id),
        )
        await db.commit()


async def mark_dose_missed(dose_log_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dose_logs SET status = 'missed', responded_at = ? WHERE id = ?",
            (datetime.now().isoformat(), dose_log_id),
        )
        await db.commit()


async def get_pending_doses(medicine_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM dose_logs WHERE medicine_id = ? AND status = 'pending' ORDER BY reminded_at DESC",
            (medicine_id,),
        ) as cur:
            return await cur.fetchall()


async def get_today_logs(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT dl.*, m.name as medicine_name, m.dosage
               FROM dose_logs dl
               JOIN medicines m ON dl.medicine_id = m.id
               WHERE m.user_id = ? AND date(dl.created_at) = ?
               ORDER BY dl.scheduled_time""",
            (user_id, today),
        ) as cur:
            return await cur.fetchall()


# ── Family Link Operations ───────────────────────────────────────

async def add_family_link(patient_user_id: int, family_user_id: int, relationship: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO family_links (patient_user_id, family_user_id, relationship)
               VALUES (?, ?, ?)
               ON CONFLICT(patient_user_id, family_user_id) DO UPDATE SET relationship=?""",
            (patient_user_id, family_user_id, relationship, relationship),
        )
        await db.commit()


async def get_family_members(patient_user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM family_links WHERE patient_user_id = ?",
            (patient_user_id,),
        ) as cur:
            return await cur.fetchall()


async def remove_family_link(patient_user_id: int, family_user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM family_links WHERE patient_user_id = ? AND family_user_id = ?",
            (patient_user_id, family_user_id),
        )
        await db.commit()
