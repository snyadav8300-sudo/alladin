# Telegram Referral Bonus Bot

## Overview
A Telegram bot for managing referral bonus claims with a single referral code. Users complete bonus requirements and submit their platform username for verification. Admins can track, approve, or reject submissions through an admin panel.

**Current State:** Bot is running with single referral code support. Ready for production use.

## Recent Changes
- **2024-11-17:** Simplified to single referral code
  - Removed multi-referral selection step (now 2-step flow instead of 3)
  - Users are automatically assigned the single configured referral code
  - Simplified user experience - no code selection needed
  - Updated admin stats and export to reflect single code setup
  - Fixed security vulnerability requiring admin authentication

- **2024-11-17:** Initial project setup with complete bot implementation
  - Created main.py with aiogram 3.x bot
  - Configured SQLite database for user tracking
  - Added health check server for Render deployment on port 8080
  - Set up admin commands for user management

## Project Architecture

### Technology Stack
- **Language:** Python 3.11
- **Framework:** aiogram 3.15.0 (Telegram Bot API)
- **Database:** SQLite with schema migrations
- **Web Server:** aiohttp (health check endpoint)
- **State Management:** FSM (Finite State Machine) for user flows

### Project Structure
```
.
├── main.py              # Main bot application
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not committed)
├── .env.example         # Template for environment variables
├── bot.db              # SQLite database (auto-created)
└── replit.md           # This file
```

### Key Features
1. **Single Referral Code**
   - One referral code configured via environment variables
   - Automatically assigned to all users
   - Simpler setup and management

2. **User Flow (2 Steps)**
   - Step 1: Complete requirements (deposit & wager)
   - Step 2: Submit platform username

3. **Admin Panel**
   - `/setstatus <telegram_id> <status>` - Update user verification status
   - `/stats` - View bot statistics by status and referral code
   - `/export` - Export all users to CSV
   - `/broadcast <text>` - Send message to all users

4. **Database Schema**
   - Users table with: telegram_id, username, referral_agent, status, etc.
   - Automatic migrations for schema updates
   - Indexed queries for performance

5. **Deployment**
   - Render-compatible with `/tmp` database storage
   - Health check endpoint on port 8080
   - Auto-restart on bot conflicts

## Configuration

### Required Environment Variables
```bash
BOT_TOKEN=              # From @BotFather on Telegram
ADMIN_USER_ID=          # Your Telegram user ID (required for security)
REF_CODE=               # Your referral code name
REF_LINK=               # Your referral link
```

### Optional Environment Variables
```bash
ADMIN_CHANNEL_ID=       # Channel ID for admin notifications (optional)
BRAND_NAME=             # Bot display name (default: "Referral Bonus Bot")
PORT=                   # Health check port (default: 8080)
RATE_LIMIT_SECONDS=     # Anti-spam delay (default: 3)
DB_PATH=                # Database file location (default: bot.db)
```

### How to Get Required Values

**BOT_TOKEN:**
1. Message @BotFather on Telegram
2. Use `/newbot` command
3. Follow prompts to create your bot
4. Copy the token provided

**ADMIN_CHANNEL_ID:**
1. Create a Telegram channel
2. Add @userinfobot to the channel
3. Forward a message from the channel to @userinfobot
4. Copy the channel ID (includes negative sign)

**ADMIN_USER_ID:**
1. Message @userinfobot on Telegram
2. Copy your user ID

**Referral Code:**
- Set REF_CODE to your referral code name (e.g., "PROMO42")
- Set REF_LINK to your referral signup link
- All users will automatically use this referral code

### Optional Variables  
- `BRAND_NAME` - Bot display name (default: "Referral Bonus Bot")
- `PORT` - Health check server port (default: 8080)
- `RATE_LIMIT_SECONDS` - Anti-spam delay (default: 3)
- `DB_PATH` - Database file location (default: bot.db)

## User Preferences
- No specific preferences documented yet

## Development Notes

### Database Migrations
The bot automatically handles schema migrations. When the `referral_agent` column was added, existing databases are migrated automatically on startup.

### Rate Limiting
Built-in rate limiter prevents spam (3-second default cooldown between actions per user).

### Error Handling
- Bot conflicts auto-retry after 5 seconds
- General errors auto-retry after 10 seconds
- Admin notifications continue even if forwarding fails

### Deployment on Render
The bot is configured to work on Render with:
- Database stored in `/tmp/bot.db` (ephemeral)
- Health check on port 8080 for keep-alive
- Proper signal handling for graceful shutdown

## Next Steps
1. Set up environment variables with real values
2. Test bot in development
3. Deploy to Render or similar platform
4. Monitor admin channel for submissions
