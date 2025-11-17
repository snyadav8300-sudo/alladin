ADMIN_CHANNEL_ID, text=summary, disable_web_page_preview=True)
            forwarded_ok = True
        except Exception:
            forwarded_ok = False

        if forwarded_ok:
            await message.answer(
                divider() +
                "\n<b>🎉 Submission Complete! ✅</b>\n\n"
                "Thank you! We'll verify your details within 24-48 hours.\n\n"
                "<b>Verification includes:</b>\n"
                "• Account creation with our code\n"
                "• $42 deposit and wager\n"
                "• New user status\n\n"
                "You'll receive a confirmation message when your bonus is approved." +
                divider(),
                reply_markup=menu_kb(),
                disable_web_page_preview=True
            )
        else:
            await message.answer(
                "✅ <b>Submission Received!</b>\n\n"
                "Your details have been saved. Our team will review them shortly.\n\n"
                "<b>Note:</b> We'll verify your account meets all requirements.",
                reply_markup=menu_kb(),
                disable_web_page_preview=True
            )

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
