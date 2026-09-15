import aiosqlite
from datetime import datetime, timedelta
import discord


class Database:
    def __init__(self):
        self.db_path = "giveaways.db"
        self.db = None

    async def init_db(self):
        if self.db is None:
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute("PRAGMA journal_mode=WAL")
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    prize TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    winners INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    required_role_id TEXT,
                    min_account_age INTEGER DEFAULT 0,
                    creator_id TEXT NOT NULL
                )
            """)
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    giveaway_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    entered_at TEXT NOT NULL,
                    PRIMARY KEY (giveaway_id, user_id)
                )
            """)
            await self.db.commit()

    async def create_giveaway(self, message_id, channel_id, guild_id, prize, duration, winners, required_role_id, min_account_age, creator_id):
        now = datetime.now()
        ends_at = now + timedelta(seconds=duration)
        cursor = await self.db.execute(
            """
            INSERT INTO giveaways
            (message_id, channel_id, guild_id, prize, duration, winners, status,
             created_at, ends_at, required_role_id, min_account_age, creator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(message_id), str(channel_id), str(guild_id), prize,
                int(duration), int(winners), "active", now.isoformat(),
                ends_at.isoformat(),
                str(required_role_id) if required_role_id else None,
                int(min_account_age or 0), str(creator_id),
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_giveaway(self, giveaway_id):
        cursor = await self.db.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(zip([d[0] for d in cursor.description], row))

    async def get_active_giveaways(self, guild_id=None):
        if guild_id is None:
            cursor = await self.db.execute("SELECT * FROM giveaways WHERE status = 'active'")
        else:
            cursor = await self.db.execute(
                "SELECT * FROM giveaways WHERE guild_id = ? AND status = 'active'",
                (str(guild_id),),
            )
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def get_giveaway_by_message(self, message_id, channel_id):
        cursor = await self.db.execute(
            "SELECT * FROM giveaways WHERE message_id = ? AND channel_id = ?",
            (str(message_id), str(channel_id)),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(zip([d[0] for d in cursor.description], row))

    async def add_entry(self, giveaway_id, user_id):
        await self.db.execute(
            "INSERT OR IGNORE INTO entries (giveaway_id, user_id, entered_at) VALUES (?, ?, ?)",
            (giveaway_id, str(user_id), datetime.now().isoformat()),
        )
        await self.db.commit()

    async def get_entries(self, giveaway_id):
        cursor = await self.db.execute(
            "SELECT user_id FROM entries WHERE giveaway_id = ?", (giveaway_id,)
        )
        return [row[0] for row in await cursor.fetchall()]

    async def end_giveaway(self, giveaway_id, winner_ids):
        await self.db.execute(
            "UPDATE giveaways SET status = 'ended' WHERE id = ?", (giveaway_id,)
        )
        await self.db.commit()

    async def cancel_giveaway(self, giveaway_id):
        await self.db.execute(
            "UPDATE giveaways SET status = 'cancelled' WHERE id = ?", (giveaway_id,)
        )
        await self.db.commit()

    async def reroll_giveaway(self, giveaway_id, new_winner_ids):
        return new_winner_ids

    async def check_expired_giveaways(self, bot):
        cursor = await self.db.execute("SELECT * FROM giveaways WHERE status = 'active'")
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        for row in rows:
            giveaway = dict(zip(columns, row))
            try:
                ends_at = datetime.fromisoformat(giveaway["ends_at"])
                if datetime.now() >= ends_at:
                    await self.end_giveaway_automatically(bot, giveaway)
            except Exception as exc:
                print(f"Error checking giveaway {giveaway.get('id')}: {exc}")

    async def end_giveaway_automatically(self, bot, giveaway):
        try:
            channel = bot.get_channel(int(giveaway["channel_id"]))
            if channel is None:
                channel = await bot.fetch_channel(int(giveaway["channel_id"]))

            message = await channel.fetch_message(int(giveaway["message_id"]))
            entries = await self.get_entries(giveaway["id"])

            if not entries:
                await message.edit(
                    content=(
                        "🎉 **GIVEAWAY ENDED**\n\n"
                        f"🎁 Prize: {giveaway['prize']}\n"
                        "⏰ Time's up!\n"
                        "👥 No valid entries."
                    ),
                    embed=None,
                    view=None,
                )
                await self.end_giveaway(giveaway["id"], [])
                return

            import random
            winners = random.sample(entries, min(int(giveaway["winners"]), len(entries)))
            mentions = ", ".join(f"<@{user_id}>" for user_id in winners)

            embed = discord.Embed(title="🎉 GIVEAWAY ENDED", color=0xFF6B6B)
            embed.add_field(name="Prize", value=giveaway["prize"], inline=False)
            embed.add_field(name="Winners", value=mentions, inline=False)
            embed.add_field(name="Total Entries", value=str(len(entries)), inline=False)

            await message.edit(content=None, embed=embed, view=None)

            # Send a fresh winner announcement message so Discord sends a new notification/ping.
            try:
                await channel.send(
                    content=f"🎉 **GIVEAWAY WINNER{'S' if len(winners) != 1 else ''}!** {mentions}\n"
                            f"Congratulations! You won **{giveaway['prize']}**!",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.HTTPException as exc:
                print(f"Could not send winner announcement for giveaway {giveaway['id']}: {exc}")

            for winner_id in winners:
                try:
                    user = await bot.fetch_user(int(winner_id))
                    await user.send(
                        f"🎉 Congratulations! You won the giveaway for **{giveaway['prize']}**!"
                    )
                except (discord.HTTPException, discord.Forbidden):
                    pass

            await self.end_giveaway(giveaway["id"], winners)
        except Exception as exc:
            print(f"Error ending giveaway {giveaway.get('id')}: {exc}")

    async def close(self):
        if self.db is not None:
            await self.db.close()
            self.db = None
