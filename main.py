#!/usr/bin/env python3
"""
Telegram Referral Bonus Bot
A bot for managing referral bonus claims with admin verification
"""

import os
import sys
import signal
import asyncio
import sqlite3
import csv
import tempfile
from datetime import datetime
from pathlib import Path
from contextlib import closing
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError

# Load environment variables
load_dotenv()

# -------------------------
# Configuration
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) or None
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID") or None
REF_CODE = os.getenv("REF_CODE", "PROMO42")
REF_LINK = os.getenv("REF_LINK", "https://example.com/signup?ref=PROMO42")
BRAND_NAME = os.getenv("BRAND_NAME", "Referral Bonus Bot")
PORT = int(os.getenv("PORT", 8080))
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", 3))
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Global instances
bot_instance = None
dp_instance = None
health_runner = None

# Rate limiting
user_last_action = {}

# -------------------------
# FSM States
# -------------------------
class BonusFlow(StatesGroup):
    awaiting_platform_username = State()

# -------------------------
# Database Functions
# -------------------------
def db_connect():
    """Connect to SQLite database with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    """Initialize database with schema and migrations"""
    with closing(db_connect()) as conn:
        # Create users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                tg_username TEXT,
                referral_agent TEXT,
                signed_up INTEGER DEFAULT 0,
                bonus_claimed INTEGER DEFAULT 0,
                platform_username TEXT,
                status TEXT DEFAULT 'Pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if referral_agent column exists, add if missing (migration)
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "referral_agent" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN referral_agent TEXT")
        
        conn.commit()

def get_or_create_user(telegram_id: int, username: str = None):
    """Get existing user or create new one"""
    with closing(db_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        
        if row:
            return dict(row)
        
        # Create new user with single referral code
        conn.execute(
            """
            INSERT INTO users (telegram_id, tg_username, referral_agent)
            VALUES (?, ?, ?)
            """,
            (telegram_id, username, REF_CODE)
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row)

def mark_signed_up(telegram_id: int):
    """Mark user as signed up"""
    with closing(db_connect()) as conn:
        conn.execute(
            "UPDATE users SET signed_up = 1, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (telegram_id,)
        )
        conn.commit()

def save_platform_username(telegram_id: int, platform_username: str):
    """Save platform username"""
    with closing(db_connect()) as conn:
        conn.execute(
            """
            UPDATE users 
            SET platform_username = ?, bonus_claimed = 1, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (platform_username, telegram_id)
        )
        conn.commit()

def set_status(telegram_id: int, status: str) -> bool:
    """Set user status (Pending, Verified, Rejected)"""
    with closing(db_connect()) as conn:
        cursor = conn.execute(
            "SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        if not cursor.fetchone():
            return False
        
        conn.execute(
            "UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (status, telegram_id)
        )
        conn.commit()
        return True

# -------------------------
# Helper Functions
# -------------------------
def divider():
    """Return a visual divider"""
    return "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

def line():
    """Return a thin line"""
    return "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

def header(text: str) -> str:
    """Return a formatted header"""
    return f"\n{'━' * 30}\n   {text}\n{'━' * 30}\n"

def menu_kb():
    """Return main menu keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Claim Bonus")],
            [KeyboardButton(text="📊 My Status"), KeyboardButton(text="ℹ️ Help")]
        ],
        resize_keyboard=True
    )

def bonus_kb():
    """Return bonus claim keyboard with Done button"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Done")],
            [KeyboardButton(text="📊 My Status"), KeyboardButton(text="ℹ️ Help")]
        ],
        resize_keyboard=True
    )

def can_proceed(user_id: int) -> bool:
    """Rate limiting check"""
    now = datetime.utcnow().timestamp()
    last = user_last_action.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    user_last_action[user_id] = now
    return True

# -------------------------
# Bot Initialization
# -------------------------
def initialize_bot():
    """Initialize bot, dispatcher, and router"""
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    router = Router()
    dp.include_router(router)
    
    return bot, dp, router

# -------------------------
# Handler Registration
# -------------------------
def register_handlers(router: Router, bot: Bot):
    """Register all bot handlers"""
    
    # -------------------------
    # User Commands
    # -------------------------
    @router.message(CommandStart())
    async def start_cmd(message: Message):
        user = get_or_create_user(message.from_user.id, message.from_user.username)
        
        welcome = f"🎁 <b>Welcome to {BRAND_NAME}!</b>\n"
        welcome += divider()
        welcome += f"💵 <b>Get Your $42 Bonus</b>\n\n"
        welcome += f"<b>How it works:</b>\n"
        welcome += f"  1. Sign up with our code\n"
        welcome += f"  2. Deposit $42 + wager\n"
        welcome += f"  3. Submit your username\n"
        welcome += f"  4. Get approved!\n"
        welcome += line()
        welcome += f"📋 <b>Code:</b> <code>{REF_CODE}</code>\n"
        welcome += f"🔗 <b>Link:</b> {REF_LINK}\n"
        welcome += divider()
        welcome += f"👇 Tap <b>Claim Bonus</b> to start"
        
        await message.answer(welcome, reply_markup=menu_kb(), disable_web_page_preview=True)
    
    @router.message(F.text == "💰 Claim Bonus")
    async def claim_bonus_btn(message: Message, state: FSMContext):
        if not can_proceed(message.from_user.id):
            await message.answer("⏱ Please wait a moment...", disable_web_page_preview=True)
            return
        
        user = get_or_create_user(message.from_user.id, message.from_user.username)
        
        txt = f"💰 <b>Claim Your $42 Bonus</b>\n"
        txt += divider()
        txt += f"<b>Step 1:</b> Complete Requirements\n\n"
        txt += f"  ▸ Sign up using the link below\n"
        txt += f"  ▸ Use code: <code>{REF_CODE}</code>\n"
        txt += f"  ▸ Deposit $42 and place a wager\n"
        txt += line()
        txt += f"🔗 {REF_LINK}\n"
        txt += divider()
        txt += f"<b>Step 2:</b> Tap <b>Done</b> when ready"
        
        await message.answer(txt, reply_markup=bonus_kb(), disable_web_page_preview=True)
    
    @router.message(F.text == "✅ Done")
    async def done_requirements(message: Message, state: FSMContext):
        mark_signed_up(message.from_user.id)
        
        txt = f"✅ <b>Great!</b>\n\n"
        txt += f"Now send your <b>platform username</b>\n"
        txt += f"so we can verify your account."
        
        await message.answer(txt, reply_markup=menu_kb(), disable_web_page_preview=True)
        await state.set_state(BonusFlow.awaiting_platform_username)
    
    @router.message(F.text == "📊 My Status")
    async def status_btn(message: Message):
        user = get_or_create_user(message.from_user.id, message.from_user.username)
        
        status_icon = {"Pending": "⏳", "Verified": "✅", "Rejected": "❌"}.get(user['status'], "❓")
        
        txt = f"📊 <b>Your Status</b>\n"
        txt += divider()
        txt += f"<b>ID:</b> <code>{user['telegram_id']}</code>\n"
        txt += f"<b>Username:</b> {user['platform_username'] or '—'}\n"
        txt += f"<b>Status:</b> {status_icon} {user['status']}\n"
        txt += divider()
        
        if user['status'] == 'Pending':
            txt += "Your submission is being reviewed."
        elif user['status'] == 'Verified':
            txt += "Your bonus has been approved! 🎉"
        elif user['status'] == 'Rejected':
            txt += "Contact support for details."
        
        await message.answer(txt, reply_markup=menu_kb(), disable_web_page_preview=True)
    
    @router.message(F.text == "ℹ️ Help")
    async def help_btn(message: Message):
        txt = f"ℹ️ <b>Help</b>\n"
        txt += divider()
        txt += f"<b>How to claim your bonus:</b>\n\n"
        txt += f"  1. Sign up → {REF_LINK}\n"
        txt += f"  2. Use code: <code>{REF_CODE}</code>\n"
        txt += f"  3. Deposit $42 + wager\n"
        txt += f"  4. Submit username\n"
        txt += f"  5. Wait 24-48 hrs\n"
        txt += divider()
        txt += f"Questions? Contact support."
        
        await message.answer(txt, reply_markup=menu_kb(), disable_web_page_preview=True)
    
    @router.message(BonusFlow.awaiting_platform_username)
    async def receive_platform_username(message: Message, state: FSMContext):
        platform_username = message.text.strip()
        
        if not platform_username or len(platform_username) < 2:
            await message.answer("⚠️ Please enter a valid username.", disable_web_page_preview=True)
            return
        
        save_platform_username(message.from_user.id, platform_username)
        
        user = get_or_create_user(message.from_user.id, message.from_user.username)
        
        # Prepare simplified admin notification
        tg_handle = f"@{user['tg_username']}" if user['tg_username'] else "—"
        
        summary = f"🆕 <b>New Submission</b>\n"
        summary += f"┌ User: {tg_handle}\n"
        summary += f"├ Platform: <code>{platform_username}</code>\n"
        summary += f"└ ID: <code>{user['telegram_id']}</code>\n\n"
        summary += f"<code>/setstatus {user['telegram_id']} Verified</code>"
        
        # Try to send to admin channel
        forwarded_ok = False
        try:
            await bot.send_message(
                ADMIN_CHANNEL_ID, text=summary, disable_web_page_preview=True)
            forwarded_ok = True
        except Exception:
            forwarded_ok = False

        # User confirmation message
        confirm_txt = f"🎉 <b>Submitted!</b>\n"
        confirm_txt += divider()
        confirm_txt += f"Username: <code>{platform_username}</code>\n\n"
        confirm_txt += f"We'll verify within 24-48 hours.\n"
        confirm_txt += f"You'll be notified when approved."
        
        await message.answer(confirm_txt, reply_markup=menu_kb(), disable_web_page_preview=True)
        await state.clear()

    # -------------------------
    # Admin Commands
    # -------------------------
    @router.message(Command("setstatus"))
    async def setstatus_cmd(message: Message):
        in_admin_channel = str(message.chat.id) == str(ADMIN_CHANNEL_ID)
        from_admin_user = ADMIN_USER_ID and (message.from_user.id == ADMIN_USER_ID)

        if not (in_admin_channel or from_admin_user):
            await message.reply("Not allowed here.", disable_web_page_preview=True)
            return

        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.reply("Usage: /setstatus <telegram_id> <Pending|Verified|Rejected>", disable_web_page_preview=True)
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await message.reply("Invalid telegram_id.", disable_web_page_preview=True)
            return

        new_status = parts[2].capitalize()
        if new_status not in {"Pending", "Verified", "Rejected"}:
            await message.reply("Status must be Pending, Verified, or Rejected.", disable_web_page_preview=True)
            return

        ok = set_status(target_id, new_status)
        if not ok:
            await message.reply("User not found in database.", disable_web_page_preview=True)
            return

        await message.reply(f"Updated status for {target_id} → <b>{new_status}</b>", disable_web_page_preview=True)

        try:
            await bot.send_message(chat_id=target_id, text=f"🔔 Your verification status is now: <b>{new_status}</b>", disable_web_page_preview=True)
        except Exception:
            pass

    @router.message(Command("export"))
    async def export_csv_cmd(message: Message):
        in_admin_channel = str(message.chat.id) == str(ADMIN_CHANNEL_ID)
        from_admin_user = ADMIN_USER_ID and (message.from_user.id == ADMIN_USER_ID)
        if not (in_admin_channel or from_admin_user):
            await message.reply("Not allowed.", disable_web_page_preview=True)
            return

        with closing(db_connect()) as conn:
            rows = conn.execute(
                "SELECT telegram_id, tg_username, referral_agent, signed_up, bonus_claimed, platform_username, status, updated_at FROM users"
            ).fetchall()

        tmp_path = Path(tempfile.gettempdir()) / f"users_export_{int(datetime.utcnow().timestamp())}.csv"
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "telegram_id",
                "tg_username",
                "referral_agent",
                "signed_up",
                "bonus_claimed",
                "platform_username",
                "status",
                "updated_at",
            ])
            for r in rows:
                w.writerow([
                    r["telegram_id"],
                    r["tg_username"],
                    REF_CODE,
                    r["signed_up"],
                    r["bonus_claimed"],
                    r["platform_username"],
                    r["status"],
                    r["updated_at"],
                ])

        await message.answer_document(FSInputFile(str(tmp_path)), caption="Exported users CSV")

    @router.message(Command("stats"))
    async def stats_cmd(message: Message):
        in_admin_channel = str(message.chat.id) == str(ADMIN_CHANNEL_ID)
        from_admin_user = ADMIN_USER_ID and (message.from_user.id == ADMIN_USER_ID)
        if not (in_admin_channel or from_admin_user):
            await message.reply("Not allowed.", disable_web_page_preview=True)
            return

        with closing(db_connect()) as conn:
            # Status counts
            status_rows = conn.execute("SELECT status, COUNT(*) AS c FROM users GROUP BY status").fetchall()
            # Total users
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        txt = header("Bot Statistics") + "\n\n"
        txt += f"<b>Referral Code:</b> <code>{REF_CODE}</code>\n"
        txt += f"<b>Total Users:</b> {total_users}\n\n"
        
        txt += "<b>By Status:</b>\n"
        for r in status_rows:
            txt += f"• {r['status']}: {r['c']}\n"

        await message.reply(txt, disable_web_page_preview=True)

    @router.message(Command("broadcast"))
    async def broadcast_cmd(message: Message):
        in_admin_channel = str(message.chat.id) == str(ADMIN_CHANNEL_ID)
        from_admin_user = ADMIN_USER_ID and (message.from_user.id == ADMIN_USER_ID)
        if not (in_admin_channel or from_admin_user):
            await message.reply("Not allowed.", disable_web_page_preview=True)
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Usage: /broadcast <text>", disable_web_page_preview=True)
            return

        text_to_send = parts[1]

        with closing(db_connect()) as conn:
            user_ids = [row[0] for row in conn.execute("SELECT telegram_id FROM users").fetchall()]

        sent = 0
        for uid in user_ids:
            try:
                await bot.send_message(chat_id=uid, text=text_to_send, disable_web_page_preview=True)
                sent += 1
                await asyncio.sleep(0.03)
            except Exception:
                pass

        await message.reply(f"Broadcast sent to <b>{sent}</b> users.", disable_web_page_preview=True)

# -------------------------
# Health Check Server for Render (Port 8080)
# -------------------------
from aiohttp import web

async def health_check(request):
    """Health check endpoint for Render"""
    return web.Response(text="✅ Telegram Referral Bot is running!")

async def start_health_server():
    """Start health check server on specified port"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"✅ Health check server running on port {PORT}")
    print(f"🌐 Health check available at: http://0.0.0.0:{PORT}/health")
    
    return runner

# -------------------------
# Signal Handlers for Clean Shutdown
# -------------------------
def signal_handler(signum, frame):
    print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
    sys.exit(0)

# -------------------------
# Main Application
# -------------------------
async def run_bot():
    """Run the Telegram bot with conflict handling"""
    global bot_instance, dp_instance
    
    print("🤖 Starting Telegram Referral Bot...")
    
    # Initialize bot
    bot_instance, dp_instance, router = initialize_bot()
    
    # Register handlers
    register_handlers(router, bot_instance)
    
    # Test connection
    try:
        me = await bot_instance.get_me()
        print(f"✅ Bot connected: @{me.username}")
    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        return
    
    # Initialize database
    db_init()
    print("📊 Database ready")
    print("🔄 Starting polling...")
    
    # Start bot polling with conflict handling
    try:
        await dp_instance.start_polling(bot_instance, allowed_updates=["message", "callback_query"])
    except TelegramConflictError as e:
        print(f"❌ Bot conflict detected: {e}")
        print("💡 Solution: Make sure only one instance of the bot is running")
        print("🔄 Restarting bot in 5 seconds...")
        await asyncio.sleep(5)
        await run_bot()  # Restart the bot
    except Exception as e:
        print(f"❌ Polling error: {e}")
        print("🔄 Restarting bot in 10 seconds...")
        await asyncio.sleep(10)
        await run_bot()  # Restart the bot

async def main():
    """Main function to run both services"""
    global health_runner
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start health server
    health_runner = await start_health_server()
    
    try:
        # Run bot (this will run until stopped)
        await run_bot()
    except Exception as e:
        print(f"❌ Bot error: {e}")
    finally:
        # Cleanup
        print("🧹 Cleaning up resources...")
        if health_runner:
            await health_runner.cleanup()
        if bot_instance:
            await bot_instance.session.close()
        print("🛑 All services stopped")

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Telegram Referral Bot - Port 8080 Ready")
    print("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
