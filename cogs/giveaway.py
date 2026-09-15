import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta


class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name="giveaway", description="Open the giveaway panel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "🎁 **Giveaway Panel**",
            view=GiveawayMainView(self.bot),
            ephemeral=True,
        )

    @giveaway.error
    async def giveaway_error(self, interaction: discord.Interaction, error):
        message = (
            "You need **Manage Server** permission to use this command."
            if isinstance(error, app_commands.MissingPermissions)
            else f"An error occurred: {error}"
        )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class GiveawayMainView(View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="Create Giveaway", style=discord.ButtonStyle.primary, emoji="🎁")
    async def create_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(GiveawayCreateModal(self.bot))

    @discord.ui.button(label="Active Giveaways", style=discord.ButtonStyle.secondary, emoji="📋")
    async def active_button(self, interaction: discord.Interaction, button: Button):
        giveaways = await self.bot.db.get_active_giveaways(interaction.guild_id)
        if not giveaways:
            await interaction.response.send_message("No active giveaways.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Active Giveaways", color=0x00AE86)
        for giveaway in giveaways:
            ends_at = datetime.fromisoformat(giveaway["ends_at"])
            remaining = max(0, int((ends_at - datetime.now()).total_seconds()))
            embed.add_field(
                name=f"🎁 {giveaway['prize']}",
                value=f"⏰ {format_duration(remaining)} | 👥 {giveaway['winners']} winner(s)",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="End Giveaway", style=discord.ButtonStyle.danger, emoji="🛑")
    async def end_button(self, interaction: discord.Interaction, button: Button):
        giveaways = await self.bot.db.get_active_giveaways(interaction.guild_id)
        if not giveaways:
            await interaction.response.send_message("No active giveaways.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Use `/giveaway` again to manage active giveaways. Automatic ending is enabled.",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel Giveaway", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Automatic cancellation controls are not enabled yet. The giveaway will end normally.",
            ephemeral=True,
        )


class GiveawayCreateModal(Modal, title="Create Giveaway"):
    prize = TextInput(label="Prize", placeholder="Enter the prize name", max_length=100)
    duration = TextInput(label="Duration", placeholder="1h30m, 90m, 1h, 30s", max_length=20)
    winners = TextInput(label="Number of Winners", placeholder="1", max_length=5)
    required_role = TextInput(
        label="Required Role (optional)",
        placeholder="Role name, or leave empty",
        max_length=100,
        required=False,
    )
    min_age = TextInput(
        label="Minimum Account Age in Days (optional)",
        placeholder="7",
        max_length=5,
        required=False,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prize = self.prize.value.strip()
            if not prize:
                raise ValueError("Prize cannot be empty.")

            duration_seconds = parse_duration(self.duration.value)
            if duration_seconds is None or duration_seconds <= 0:
                raise ValueError("Invalid duration. Use 30s, 10m, 1h, 1h30m, or 1d.")

            winners = int(self.winners.value or "1")
            if winners < 1 or winners > 100:
                raise ValueError("Number of winners must be between 1 and 100.")

            min_age = int(self.min_age.value or "0")
            if min_age < 0:
                raise ValueError("Minimum account age cannot be negative.")

            required_role = None
            role_text = self.required_role.value.strip() if self.required_role.value else ""
            if role_text:
                role_id = extract_role_id(role_text)
                required_role = interaction.guild.get_role(role_id) if role_id else None
                if required_role is None:
                    required_role = discord.utils.find(
                        lambda role: role.name.lower() == role_text.lower(),
                        interaction.guild.roles,
                    )
                if required_role is None:
                    raise ValueError("I could not find that role. Enter the exact role name or mention it.")

            embed, view = create_giveaway_embed(
                prize, duration_seconds, winners,
                required_role.id if required_role else None,
                min_age,
                self.bot,
            )

            message = await interaction.channel.send(embed=embed, view=view)
            giveaway_id = await self.bot.db.create_giveaway(
                message.id,
                message.channel.id,
                interaction.guild.id,
                prize,
                duration_seconds,
                winners,
                required_role.id if required_role else None,
                min_age,
                interaction.user.id,
            )

            view.giveaway_id = giveaway_id
            await interaction.response.send_message("✅ Giveaway created!", ephemeral=True)

        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        except Exception as exc:
            print(f"Error creating giveaway: {exc}")
            await interaction.response.send_message("❌ Failed to create the giveaway.", ephemeral=True)


def extract_role_id(value):
    value = value.strip()
    if value.startswith("<@&") and value.endswith(">"):
        try:
            return int(value[3:-1])
        except ValueError:
            return None
    if value.isdigit():
        return int(value)
    return None


def parse_duration(value):
    value = value.lower().replace(" ", "")
    if not value:
        return None

    total = 0
    number = ""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    for char in value:
        if char.isdigit():
            number += char
        elif char in units and number:
            total += int(number) * units[char]
            number = ""
        else:
            return None

    if number:
        total += int(number)
    return total if total > 0 else None


def format_duration(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and len(parts) < 2:
        parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"


def create_giveaway_embed(prize, duration_seconds, winners, required_role_id, min_account_age, bot):
    ends_at = datetime.now() + timedelta(seconds=duration_seconds)
    embed = discord.Embed(title="🎁 GIVEAWAY", color=0xFF6B6B, timestamp=datetime.now())
    embed.add_field(name="Prize", value=prize, inline=False)
    embed.add_field(name="⏱️ Time Remaining", value=format_duration(duration_seconds), inline=True)
    embed.add_field(name="👥 Winners", value=str(winners), inline=True)

    requirements = []
    if required_role_id:
        requirements.append(f"Required Role: <@&{required_role_id}>")
    if min_account_age:
        requirements.append(f"Min Account Age: {min_account_age} days")
    embed.add_field(
        name="📋 Requirements",
        value="\n".join(requirements) if requirements else "None",
        inline=False,
    )
    embed.set_footer(text=f"Ends: {ends_at.strftime('%Y-%m-%d %H:%M:%S')}")

    view = GiveawayEntryView(bot)
    return embed, view


class GiveawayEntryView(View):
    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.giveaway_id = None
        self.bot = bot
        self.db = bot.db if bot else None

    @discord.ui.button(
        label="Enter Giveaway",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="giveaway:enter",
    )
    async def enter_button(self, interaction: discord.Interaction, button: Button):
        # Persistent views are restored after a restart without the original
        # giveaway_id, so identify the giveaway from the Discord message ID.
        if not self.bot:
            await interaction.response.send_message("Giveaway system is not ready.", ephemeral=True)
            return

        self.db = self.bot.db

        if not self.giveaway_id:
            giveaway = await self.db.get_giveaway_by_message(
                interaction.message.id,
                interaction.channel_id,
            )
            if giveaway:
                self.giveaway_id = giveaway["id"]

        if not self.giveaway_id:
            await interaction.response.send_message("Giveaway data not found.", ephemeral=True)
            return

        giveaway = await self.db.get_giveaway(self.giveaway_id)
        if not giveaway or giveaway["status"] != "active":
            await interaction.response.send_message("This giveaway is no longer active.", ephemeral=True)
            return

        ends_at = datetime.fromisoformat(giveaway["ends_at"])
        if datetime.now() >= ends_at:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        if giveaway["required_role_id"]:
            role = interaction.guild.get_role(int(giveaway["required_role_id"]))
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"You need the **{role.name}** role to enter.", ephemeral=True
                )
                return

        if int(giveaway["min_account_age"] or 0) > 0:
            created = interaction.user.created_at.replace(tzinfo=None)
            age_days = (datetime.now() - created).days
            if age_days < int(giveaway["min_account_age"]):
                await interaction.response.send_message(
                    f"Your account is too new. Minimum age: {giveaway['min_account_age']} days.",
                    ephemeral=True,
                )
                return

        entries_before = await self.db.get_entries(self.giveaway_id)
        if str(interaction.user.id) in entries_before:
            await interaction.response.send_message("You have already entered!", ephemeral=True)
            return

        await self.db.add_entry(self.giveaway_id, interaction.user.id)
        entries = await self.db.get_entries(self.giveaway_id)

        embed = discord.Embed(title="🎁 GIVEAWAY", color=0xFF6B6B, timestamp=datetime.now())
        embed.add_field(name="Prize", value=giveaway["prize"], inline=False)
        remaining = max(0, int((ends_at - datetime.now()).total_seconds()))
        embed.add_field(name="⏱️ Time Remaining", value=format_duration(remaining), inline=True)
        embed.add_field(name="👥 Winners", value=str(giveaway["winners"]), inline=True)

        requirements = []
        if giveaway["required_role_id"]:
            requirements.append(f"Required Role: <@&{giveaway['required_role_id']}>")
        if giveaway["min_account_age"]:
            requirements.append(f"Min Account Age: {giveaway['min_account_age']} days")
        embed.add_field(
            name="📋 Requirements",
            value="\n".join(requirements) if requirements else "None",
            inline=False,
        )
        embed.add_field(name="🎉 Entries", value=str(len(entries)), inline=False)

        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(
            f"✅ You entered the giveaway! There are now {len(entries)} entrant(s).",
            ephemeral=True,
        )
