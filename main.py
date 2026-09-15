import os
import asyncio
import discord
from discord.ext import commands, tasks
from cogs.giveaway import GiveawayCog, GiveawayEntryView
from database import Database


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
db = Database()
bot.db = db


async def setup_hook():
    await db.init_db()
    await bot.add_cog(GiveawayCog(bot))
    bot.add_view(GiveawayEntryView(bot))
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash command(s)")


bot.setup_hook = setup_hook


@tasks.loop(seconds=10)
async def giveaway_poller():
    try:
        await db.check_expired_giveaways(bot)
    except Exception as exc:
        print(f"Giveaway polling error: {exc}")


@giveaway_poller.before_loop
async def before_giveaway_poller():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not giveaway_poller.is_running():
        giveaway_poller.start()
    print("Bot is ready! Giveaway polling every 10 seconds.")


@bot.event
async def on_disconnect():
    print("Bot disconnected, waiting for Discord to reconnect...")


@bot.event
async def on_resumed():
    print("Bot connection resumed")


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    try:
        await bot.start(token)
    finally:
        if giveaway_poller.is_running():
            giveaway_poller.cancel()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
