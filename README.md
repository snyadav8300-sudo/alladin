# Telegram Referral Bonus Bot

A Telegram bot for managing referral bonus claims with a single referral code. Users complete bonus requirements and submit their platform username for verification. Admins can track, approve, or reject submissions through an admin panel.

## Features

- **Single Referral Code System** - All users automatically use one configured referral code
- **2-Step User Flow** - Simple bonus claim process (complete requirements → submit username)
- **Admin Commands** - Verify users, view stats, export data, and broadcast messages
- **SQLite Database** - User tracking with automatic schema migrations
- **Health Check Server** - HTTP endpoint on port 8080 for deployment monitoring
- **Auto-retry** - Handles bot conflicts and errors with automatic restart

## How to Run in Replit

1. **Set Environment Variables**
   
   Update the `.env` file with your credentials:
   
   ```bash
   BOT_TOKEN=your_bot_token_here              # REQUIRED
   ADMIN_USER_ID=your_telegram_user_id        # REQUIRED
   REF_CODE=your_referral_code                # REQUIRED
   REF_LINK=your_referral_signup_link         # REQUIRED
   
   # Optional settings
   ADMIN_CHANNEL_ID=@your_channel             # Optional
   BRAND_NAME=Referral Bonus Bot              # Optional
   PORT=8080                                  # Optional
   RATE_LIMIT_SECONDS=3                       # Optional
   DB_PATH=bot.db                             # Optional
   ```

2. **Click the Run Button**
   
   The bot will start automatically when you press Run in Replit.

3. **Verify the Bot is Running**
   
   You should see:
   ```
   ✅ Health check server running on port 8080
   ✅ Bot connected: @your_bot_username
   📊 Database ready
   🔄 Starting polling...
   ```

## Required Environment Variables

### BOT_TOKEN
Get this from Telegram's @BotFather:
1. Message @BotFather on Telegram
2. Use `/newbot` command
3. Follow the prompts to create your bot
4. Copy the token provided

### ADMIN_USER_ID
Get your Telegram user ID:
1. Message @userinfobot on Telegram
2. Copy your user ID (it's a number like `123456789`)

### REF_CODE
Your referral code name (e.g., `PROMO42`, `stakeguru666`)

### REF_LINK
Your full referral signup link (e.g., `https://stake.bet/?offer=stakeguru666&c=stakeguru666`)

## Optional Environment Variables

### ADMIN_CHANNEL_ID (Optional)
To receive submission notifications in a Telegram channel:
1. Create a Telegram channel
2. Add @userinfobot to the channel as admin
3. Forward a message from the channel to @userinfobot
4. Copy the channel ID (starts with `-` like `-1001234567890` or use @channel_username format)

### Other Optional Settings
- `BRAND_NAME` - Bot display name (default: "Referral Bonus Bot")
- `PORT` - Health check server port (default: 8080)
- `RATE_LIMIT_SECONDS` - Anti-spam delay (default: 3)
- `DB_PATH` - Database file location (default: bot.db)

## Admin Commands

Use these commands in Telegram:

- `/setstatus <telegram_id> <Pending|Verified|Rejected>` - Update user verification status
- `/stats` - View bot statistics and user counts by status
- `/export` - Download all users as CSV file
- `/broadcast <text>` - Send a message to all users

**Note:** Admin commands only work if you send them:
- From the Telegram account matching `ADMIN_USER_ID`, OR
- In the channel specified by `ADMIN_CHANNEL_ID`

## User Flow

1. User starts the bot with `/start`
2. Bot shows referral code and signup link
3. User completes requirements (signup, deposit, wager)
4. User types "Done" when ready
5. User submits their platform username
6. Admin receives notification
7. Admin verifies and approves/rejects with `/setstatus`
8. User receives status update notification

## Database

The bot uses SQLite (file: `bot.db`) to track:
- User Telegram ID and username
- Referral code assigned
- Platform username submitted
- Verification status (Pending, Verified, Rejected)
- Timestamps for creation and updates

## Troubleshooting

### "Unauthorized" Error
- Make sure your `BOT_TOKEN` is correct
- Get a fresh token from @BotFather if needed

### "Bot conflict detected"
- Only run one instance of the bot at a time
- The bot will auto-retry after 5 seconds

### Admin commands not working
- Verify `ADMIN_USER_ID` matches your Telegram user ID
- Get your ID from @userinfobot

### No notifications in admin channel
- Make sure `ADMIN_CHANNEL_ID` is correct (include `-` prefix for numeric IDs)
- Add the bot as admin to the channel
- Use @channel_username format if numeric ID doesn't work

## Project Structure

```
.
├── main.py              # Main bot application
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (YOUR CREDENTIALS)
├── .env.example         # Template for environment variables
├── .gitignore          # Git ignore rules
├── bot.db              # SQLite database (auto-created)
├── replit.md           # Project documentation
└── README.md           # This file
```

## Tech Stack

- **Python 3.11**
- **aiogram 3.22.0** - Telegram Bot API framework
- **python-dotenv** - Environment variable management
- **aiohttp** - HTTP server for health checks
- **SQLite** - Database

## Run Command

The bot runs with: `python main.py`

This starts both:
1. Health check server on port 8080
2. Telegram bot with polling

## Support

For questions about the bot functionality, refer to the code comments in `main.py` or check the project documentation in `replit.md`.
