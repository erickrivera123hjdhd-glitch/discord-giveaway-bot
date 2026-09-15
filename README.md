# Discord Giveaway Bot

A simple, polished Discord giveaway bot built with discord.py 2.x.

## Features
- Create giveaways with custom duration, prize, and requirements
- Role and account age restrictions
- Automatic winner selection
- Persistent giveaways across bot restarts
- SQLite database storage

## Setup

1. Install Python 3.11+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a Discord application at https://discord.com/developers/applications
4. Create a bot and copy the token
5. Invite the bot with this URL (replace YOUR_CLIENT_ID):
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot%20applications.commands&permissions=268468736
   ```
6. Copy `.env.example` to `.env` and add your token:
   ```
   BOT_TOKEN=your_bot_token_here
   ```

## Run

```bash
python main.py
```

## Environment Variables

- `BOT_TOKEN` - Your Discord bot token (required)

## Commands

- `/giveaway` - Opens the giveaway panel (requires Manage Server permission)