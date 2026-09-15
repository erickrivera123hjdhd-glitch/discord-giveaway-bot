import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from datetime import datetime, timedelta
import asyncio
import random

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @app_commands.command(name='giveaway', description='Open the giveaway panel') 
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction):
        view = GiveawayMainView(self.bot)
        await interaction.response.send_message('🎁 **Giveaway Panel**', view=view, ephemeral=True)

    @giveaway.error
    async def giveaway_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('You need Manage Server permission to use this command.', ephemeral=True)
        else:
            await interaction.response.send_message('An error occurred.', ephemeral=True)

class GiveawayMainView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='🎁 Create Giveaway', style=discord.ButtonStyle.primary, emoji='🎁')
    async def create_button(self, interaction: discord.Interaction, button: Button):
        modal = GiveawayCreateModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='📋 Active Giveaways', style=discord.ButtonStyle.secondary, emoji='📋')
    async def active_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        giveaways = await self.bot.db.get_active_giveaways(interaction.guild_id)
        if not giveaways:
            await interaction.followup.send('No active giveaways.', ephemeral=True)
            return
        embed = discord.Embed(title='📋 Active Giveaways', color=0x00ae86)
        for g in giveaways:
            ends_at = datetime.fromisoformat(g['ends_at'])
            remaining = ends_at - datetime.now()
            hours, remainder = divmod(remaining.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f'{int(hours)}h {int(minutes)}m' if hours > 0 else f'{int(minutes)}m {int(seconds)}s'
            embed.add_field(name=f'🎁 {g["prize"]}', value=f'⏰ {time_str} | 👥 {g["winners"]} winner(s)', inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label='🏆 Reroll Winner', style=discord.ButtonStyle.success, emoji='🏆')
    async def reroll_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message('This feature requires selecting a specific giveaway. Use the bot commands for advanced management.', ephemeral=True)

    @discord.ui.button(label='🛑 End Giveaway', style=discord.ButtonStyle.danger, emoji='🛑')
    async def end_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message('This feature requires selecting a specific giveaway. Use the bot commands for advanced management.', ephemeral=True)

    @discord.ui.button(label='❌ Cancel Giveaway', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message('This feature requires selecting a specific giveaway. Use the bot commands for advanced management.', ephemeral=True)

class GiveawayCreateModal(Modal, title='Create Giveaway'):
    prize = TextInput(label='Prize', placeholder='Enter the prize name', max_length=100)
    duration = TextInput(label='Duration (e.g., 1h30m or 90m)', placeholder='1h', max_length=20)
    winners = TextInput(label='Number of Winners', placeholder='1', max_length=5)
    required_role = TextInput(label='Required Role (optional, leave empty)', placeholder='@Role', max_length=100, required=False)
    min_age = TextInput(label='Minimum Account Age in Days (optional)', placeholder='7', max_length=5, required=False)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prize = self.prize.value
            duration_str = self.duration.value
            winners = int(self.winners.value) if self.winners.value else 1
            required_role_str = self.required_role.value.strip() if self.required_role.value else None
            min_age_str = self.min_age.value.strip() if self.min_age.value else None

            duration_seconds = parse_duration(duration_str)
            if duration_seconds is None or duration_seconds <= 0:
                await interaction.response.send_message('Invalid duration format. Use formats like: 1h30m, 90m, 1h, 30s', ephemeral=True)
                return

            required_role = None
            if required_role_str:
                role = interaction.guild.get_role_named(required_role_str) or discord.utils.get(interaction.guild.roles, name=required_role_str)
                if role:
                    required_role = role.id

            min_account_age = int(min_age_str) if min_age_str else 0

            embed, view = create_giveaway_embed(prize, duration_seconds, winners, required_role, min_account_age)
            msg = await interaction.channel.send(embed=embed, view=view)

            giveaway_id = await self.bot.db.create_giveaway(
                msg.id, msg.channel_id, interaction.guild_id, prize, duration_seconds, winners, required_role, min_account_age, interaction.user.id
            )

            view.giveaway_id = giveaway_id
            view.bot = self.bot
            view.db = self.bot.db

            await interaction.response.send_message(f'✅ Giveaway created!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'Error creating giveaway: {str(e)}', ephemeral=True)

def parse_duration(duration_str: str) -> int:
    duration_str = duration_str.lower().strip()
    total_seconds = 0
    current_number = ''
    for char in duration_str:
        if char.isdigit():
            current_number += char
        else:
            if current_number:
                num = int(current_number)
                if char == 's' or char == 's':
                    total_seconds += num
                elif char == 'm':
                    total_seconds += num * 60
                elif char == 'h':
                    total_seconds += num * 3600
                elif char == 'd':
                    total_seconds += num * 86400
                current_number = ''
    if current_number:
        total_seconds += int(current_number)
    return total_seconds if total_seconds > 0 else None

def create_giveaway_embed(prize, duration_seconds, winners, required_role_id, min_account_age):
    ends_at = datetime.now() + timedelta(seconds=duration_seconds)
    remaining = ends_at - datetime.now()
    hours, remainder = divmod(remaining.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    time_str = f'{int(hours)}h {int(minutes)}m' if hours > 0 else f'{int(minutes)}m' if minutes > 0 else f'{int(seconds)}s'

    embed = discord.Embed(title='🎁 GIVEAWAY', color=0xff6b6b, timestamp=datetime.now())
    embed.add_field(name='Prize', value=prize, inline=False)
    embed.add_field(name='⏱️ Time Remaining', value=time_str, inline=True)
    embed.add_field(name='👥 Winners', value=str(winners), inline=True)
    requirements = []
    if required_role_id:
        requirements.append(f'Required Role: <@&{required_role_id}>')
    if min_account_age:
        requirements.append(f'Min Account Age: {min_account_age} days')
    if requirements:
        embed.add_field(name='📋 Requirements', value='\n'.join(requirements), inline=False)
    else:
        embed.add_field(name='📋 Requirements', value='None', inline=False)

    view = GiveawayEntryView()
    view.giveaway_id = None
    view.bot = None
    view.db = None

    return embed, view

class GiveawayEntryView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.giveaway_id = None
        self.bot = None
        self.db = None

    @discord.ui.button(label='🎉 Enter Giveaway', style=discord.ButtonStyle.success, emoji='🎉')
    async def enter_button(self, interaction: discord.Interaction, button: Button):
        if not self.giveaway_id or not self.bot or not self.db:
            await interaction.response.send_message('Giveaway data not found.', ephemeral=True)
            return

        giveaway = await self.db.get_giveaway(self.giveaway_id)
        if not giveaway or giveaway['status'] != 'active':
            await interaction.response.send_message('This giveaway is no longer active.', ephemeral=True)
            return

        user_id = interaction.user.id
        entries = await self.db.get_entries(self.giveaway_id)
        if str(user_id) in entries:
            await interaction.response.send_message('You have already entered this giveaway!', ephemeral=True)
            return

        if giveaway['required_role_id']:
            required_role = interaction.guild.get_role(int(giveaway['required_role_id']))
            if required_role and required_role not in interaction.user.roles:
                await interaction.response.send_message(f'You need the {required_role.name} role to enter.', ephemeral=True)
                return

        if giveaway['min_account_age'] and giveaway['min_account_age'] > 0:
            account_age = (datetime.now() - interaction.user.created_at.replace(tzinfo=None)).days
            if account_age < giveaway['min_account_age']:
                await interaction.response.send_message(f'Your account is too new. Minimum age: {giveaway["min_account_age"]} days.', ephemeral=True)
                return

        await self.db.add_entry(self.giveaway_id, user_id)
        entries = await self.db.get_entries(self.giveaway_id)

        embed = interaction.message.embeds[0]
        new_embed = discord.Embed(title='🎁 GIVEAWAY', color=0xff6b6b, timestamp=datetime.now())
        new_embed.add_field(name='Prize', value=giveaway['prize'], inline=False)

        ends_at = datetime.fromisoformat(giveaway['ends_at'])
        remaining = ends_at - datetime.now()
        hours, remainder = divmod(remaining.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f'{int(hours)}h {int(minutes)}m' if hours > 0 else f'{int(minutes)}m' if minutes > 0 else f'{int(seconds)}s'

        new_embed.add_field(name='⏱️ Time Remaining', value=time_str, inline=True)
        new_embed.add_field(name='👥 Winners', value=str(giveaway['winners']), inline=True)

        requirements = []
        if giveaway['required_role_id']:
            requirements.append(f'Required Role: <@&{giveaway["required_role_id"]}>')
        if giveaway['min_account_age']:
            requirements.append(f'Min Account Age: {giveaway["min_account_age"]} days')
        if requirements:
            new_embed.add_field(name='📋 Requirements', value='\n'.join(requirements), inline=False)
        else:
            new_embed.add_field(name='📋 Requirements', value='None', inline=False)

        new_embed.add_field(name='🎉 Entered!', value=f'You have {len(entries)} entrant(s) so far.', inline=False)

        await interaction.message.edit(embed=new_embed)
        await interaction.response.send_message(f'✅ You have entered the giveaway! ({len(entries)} entrant(s))', ephemeral=True)