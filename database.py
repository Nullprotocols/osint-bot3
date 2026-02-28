# database.py - Complete Database Module for OSINT Pro Bot
# 📅 Last updated: February 2026
# ⚡ Async SQLite3 with aiosqlite

import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Any

# Import database path from config
try:
    from config import DB_PATH
except ImportError:
    # Fallback if config not available (for testing)
    DB_PATH = "osint_bot.db"

# ==================== INITIALIZATION ====================
async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                lookups INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Admins table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Banned users table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_by INTEGER,
                banned_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Lookups log table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS lookups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                query TEXT,
                response TEXT,  -- JSON stored as text
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Groups where bot is admin (for /groups)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Settings table (optional, can be used for future features)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.commit()

# ==================== USER MANAGEMENT ====================
async def update_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Insert or update user information."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_seen = CURRENT_TIMESTAMP
        ''', (user_id, username, first_name, last_name))
        await db.commit()

async def get_user(user_id: int) -> Optional[Tuple]:
    """Get user details by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

# ==================== ADMIN MANAGEMENT ====================
async def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def add_admin(user_id: int, added_by: int):
    """Add a new admin (ignores if already exists)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)', (user_id, added_by))
        await db.commit()

async def remove_admin(user_id: int):
    """Remove an admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_all_admins() -> List[int]:
    """Get list of all admin user IDs."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM admins') as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# ==================== BAN MANAGEMENT ====================
async def is_banned(user_id: int) -> bool:
    """Check if user is banned."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM bans WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def ban_user(user_id: int, reason: str, banned_by: int):
    """Ban a user (replace if already banned)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO bans (user_id, reason, banned_by)
            VALUES (?, ?, ?)
        ''', (user_id, reason, banned_by))
        await db.commit()

async def unban_user(user_id: int):
    """Unban a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        await db.commit()

# ==================== LOOKUP LOGGING ====================
async def save_lookup(user_id: int, command: str, query: str, response: Any):
    """Save lookup to database. response can be dict/list; we store as JSON."""
    resp_json = json.dumps(response, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO lookups (user_id, command, query, response)
            VALUES (?, ?, ?, ?)
        ''', (user_id, command, query, resp_json))
        # Increment user's lookup count
        await db.execute('UPDATE users SET lookups = lookups + 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_user_lookups(user_id: int, limit: int = 10) -> List[Tuple]:
    """Get last N lookups of a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT command, query, timestamp FROM lookups
            WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (user_id, limit)) as cursor:
            return await cursor.fetchall()

# ==================== STATISTICS ====================
async def get_stats() -> dict:
    """Get overall bot statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Total users
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total_users = (await cursor.fetchone())[0]
        # Total lookups
        async with db.execute('SELECT COUNT(*) FROM lookups') as cursor:
            total_lookups = (await cursor.fetchone())[0]
        # Total admins
        async with db.execute('SELECT COUNT(*) FROM admins') as cursor:
            total_admins = (await cursor.fetchone())[0]
        # Total banned
        async with db.execute('SELECT COUNT(*) FROM bans') as cursor:
            total_banned = (await cursor.fetchone())[0]
        return {
            'total_users': total_users,
            'total_lookups': total_lookups,
            'total_admins': total_admins,
            'total_banned': total_banned
        }

async def get_daily_stats(days: int = 7) -> List[Tuple]:
    """Get daily command usage stats for last N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        async with db.execute('''
            SELECT date(timestamp) as day, command, COUNT(*)
            FROM lookups
            WHERE timestamp >= ?
            GROUP BY day, command
            ORDER BY day DESC
        ''', (cutoff,)) as cursor:
            return await cursor.fetchall()

async def get_lookup_stats(limit: int = 10) -> List[Tuple]:
    """Get most used commands."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT command, COUNT(*) as cnt
            FROM lookups
            GROUP BY command
            ORDER BY cnt DESC LIMIT ?
        ''', (limit,)) as cursor:
            return await cursor.fetchall()

async def get_leaderboard(limit: int = 10) -> List[Tuple]:
    """Get top users by lookup count."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT user_id, lookups FROM users
            ORDER BY lookups DESC LIMIT ?
        ''', (limit,)) as cursor:
            return await cursor.fetchall()

# ==================== USER LISTING ====================
async def get_all_users(limit: int = 1000000, offset: int = 0) -> List[Tuple]:
    """Get all users with pagination (default high limit for broadcast)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT user_id, username, first_name, last_name, lookups, last_seen
            FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?
        ''', (limit, offset)) as cursor:
            return await cursor.fetchall()

async def get_recent_users(days: int = 7) -> List[Tuple]:
    """Get users active in last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT user_id, username, last_seen FROM users
            WHERE last_seen >= ?
            ORDER BY last_seen DESC
        ''', (cutoff,)) as cursor:
            return await cursor.fetchall()

async def get_inactive_users(days: int = 30) -> List[Tuple]:
    """Get users inactive for more than N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT user_id, username, last_seen FROM users
            WHERE last_seen < ?
            ORDER BY last_seen DESC
        ''', (cutoff,)) as cursor:
            return await cursor.fetchall()

# ==================== GROUPS MANAGEMENT (for /groups) ====================
async def add_or_update_group(chat_id: int, title: str, username: str = None, invite_link: str = None):
    """Add or update group info where bot is admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO bot_groups (chat_id, title, username, invite_link, last_active)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                username = excluded.username,
                invite_link = excluded.invite_link,
                last_active = CURRENT_TIMESTAMP
        ''', (chat_id, title, username, invite_link))
        await db.commit()

async def get_all_groups() -> List[Tuple]:
    """Get all groups where bot has been active (admin assumed)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT chat_id, title, username, invite_link
            FROM bot_groups
            ORDER BY last_active DESC
        ''') as cursor:
            return await cursor.fetchall()

# ==================== SETTINGS (optional) ====================
async def set_setting(key: str, value: str):
    """Set a bot setting."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        await db.commit()

async def get_setting(key: str) -> Optional[str]:
    """Get a bot setting."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT value FROM settings WHERE key = ?', (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
