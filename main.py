import os
import asyncio
import discord
from discord.ext import commands
from cogs.giveaway import GiveawayCog
from database import Database

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

db = Database()

bot.db = db

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    synced = await bot.tree.sync()
    print(f'Synced {len(synced)} commands')
    await db.init_db()
    await check_expired_giveaways()
    print('Bot is ready!')

async def check_expired_giveaways():
    await db.check_expired_giveaways(bot)

@bot.event
async def on_disconnect():
    print('Bot disconnected, will resume on reconnect')

@bot.event
async def on_resumed():
    print('Bot resumed connection')

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'Error in {event}: {args} {kwargs}')

bot.add_cog(GiveawayCog(bot))

bot.run(os.getenv('BOT_TOKEN'))