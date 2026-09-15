import aiosqlite
import asyncio
from datetime import datetime, timedelta
import discord

class Database:
    def __init__(self):
        self.db_path = 'giveaways.db'

    async def init_db(self):
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                channel_id TEXT,
                guild_id TEXT,
                prize TEXT,
                duration INTEGER,
                winners INTEGER,
                status TEXT,
                created_at TEXT,
                ends_at TEXT,
                required_role_id TEXT,
                min_account_age INTEGER,
                creator_id TEXT
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                giveaway_id INTEGER,
                user_id TEXT,
                entered_at TEXT,
                PRIMARY KEY (giveaway_id, user_id)
            )
        ''')
        await self.db.commit()

    async def create_giveaway(self, message_id, channel_id, guild_id, prize, duration, winners, required_role_id, min_account_age, creator_id):
        ends_at = datetime.now() + timedelta(seconds=duration)
        await self.db.execute('''
            INSERT INTO giveaways (message_id, channel_id, guild_id, prize, duration, winners, status, created_at, ends_at, required_role_id, min_account_age, creator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, str(channel_id), str(guild_id), prize, duration, winners, 'active', datetime.now().isoformat(), ends_at.isoformat(), str(required_role_id) if required_role_id else None, min_account_age, str(creator_id)))
        await self.db.commit()
        cursor = await self.db.execute('SELECT last_insert_rowid()')
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_giveaway(self, giveaway_id):
        cursor = await self.db.execute('SELECT * FROM giveaways WHERE id = ?', (giveaway_id,))
        row = await cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    async def get_active_giveaways(self, guild_id=None):
        if guild_id:
            cursor = await self.db.execute('SELECT * FROM giveaways WHERE guild_id = ? AND status = ?', (str(guild_id), 'active'))
        else:
            cursor = await self.db.execute('SELECT * FROM giveaways WHERE status = ?', ('active',))
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def get_giveaway_by_message(self, message_id, channel_id):
        cursor = await self.db.execute('SELECT * FROM giveaways WHERE message_id = ? AND channel_id = ?', (str(message_id), str(channel_id)))
        row = await cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    async def add_entry(self, giveaway_id, user_id):
        await self.db.execute('INSERT OR IGNORE INTO entries (giveaway_id, user_id, entered_at) VALUES (?, ?, ?)', (giveaway_id, str(user_id), datetime.now().isoformat()))
        await self.db.commit()

    async def get_entries(self, giveaway_id):
        cursor = await self.db.execute('SELECT user_id FROM entries WHERE giveaway_id = ?', (giveaway_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def end_giveaway(self, giveaway_id, winner_ids):
        await self.db.execute('UPDATE giveaways SET status = ? WHERE id = ?', ('ended', giveaway_id))
        await self.db.commit()

    async def cancel_giveaway(self, giveaway_id):
        await self.db.execute('UPDATE giveaways SET status = ? WHERE id = ?', ('cancelled', giveaway_id))
        await self.db.commit()

    async def reroll_giveaway(self, giveaway_id, new_winner_ids):
        pass

    async def check_expired_giveaways(self, bot):
        cursor = await self.db.execute('SELECT * FROM giveaways WHERE status = ?', ('active',))
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        for row in rows:
            giveaway = dict(zip(columns, row))
            ends_at = datetime.fromisoformat(giveaway['ends_at'])
            if datetime.now() > ends_at:
                await self.end_giveaway_automatically(bot, giveaway)

    async def end_giveaway_automatically(self, bot, giveaway):
        try:
            channel = bot.get_channel(int(giveaway['channel_id']))
            if not channel:
                return
            message = await channel.fetch_message(int(giveaway['message_id']))
            entries = await self.get_entries(giveaway['id'])
            if not entries:
                await message.edit(content=f'🎉 **GIVEAWAY ENDED**

🎁 Prize: {giveaway["prize"]}
⏰ Time's up!
👥 No valid entries.

', view=None)
                await self.end_giveaway(giveaway['id'], [])
                return
            import random
            winners = random.sample(entries, min(giveaway['winners'], len(entries)))
            winner_mentions = [f'<@{w}>' for w in winners]
            embed = discord.Embed(title='🎉 GIVEAWAY ENDED', color=0xff6b6b)
            embed.add_field(name='Prize', value=giveaway['prize'], inline=False)
            embed.add_field(name='Winners', value=', '.join(winner_mentions), inline=False)
            embed.add_field(name='Total Entries', value=len(entries), inline=False)
            await message.edit(content='', embed=embed, view=None)
            for winner_id in winners:
                try:
                    user = await bot.fetch_user(int(winner_id))
                    await user.send(f'Congratulations! You won the giveaway for: {giveaway["prize"]}')
                except:
                    pass
            await self.end_giveaway(giveaway['id'], winners)
        except Exception as e:
            print(f'Error ending giveaway: {e}')

    async def close(self):
        await self.db.close()