import os
import discord
from discord.ext import commands
from cogs.giveaway import GiveawayCog
from database import Database


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
db = Database()
bot.db = db


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready!")


@bot.event
async def on_disconnect():
    print("Bot disconnected, waiting for Discord to reconnect...")


@bot.event
async def on_resumed():
    print("Bot connection resumed")


async def setup_bot():
    await db.init_db()
    await bot.add_cog(GiveawayCog(bot))
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash command(s)")
    await db.check_expired_giveaways(bot)


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    await setup_bot()
    try:
        await bot.start(token)
    finally:
        await db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
