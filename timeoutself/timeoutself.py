import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import datetime
import re

def parse_simple_time_interval(timestr: str) -> datetime.timedelta:
    """Parse a time string of the form "3d 48h5m 6s" into a datetime.timedelta object."""
    days = re.search(r'(\d+)d', timestr)
    hours = re.search(r'(\d+)h', timestr)
    minutes = re.search(r'(\d+)m', timestr)
    seconds = re.search(r'(\d+)s', timestr)
    days = int(days.group(1)) if days else 0
    hours = int(hours.group(1)) if hours else 0
    minutes = int(minutes.group(1)) if minutes else 0
    seconds = int(seconds.group(1)) if seconds else 0
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

class TimeoutConfirm(discord.ui.View):
    msg: discord.Message | None

    def __init__(self, time: datetime.timedelta, member: discord.Member):
        super().__init__()
        self.time = time
        self.member = member
        self.timeout = 10
        self.msg = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def button_yes(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.msg is None:
            return
        if interaction.user != self.member:
            await interaction.response.send_message("You do not have permissions to press that button!", ephemeral=True)
            return
        try:
            await self.member.timeout(self.time, reason="self-requested via command")
        except discord.Forbidden:
            await interaction.response.send_message("Missing permissions")
            return
        timestamp = int((datetime.datetime.now() + self.time).timestamp())
        await self.msg.edit(content=f"Timed out until <t:{timestamp}:F> (<t:{timestamp}:R>)", view=None)
        self.msg = None
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def button_no(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.msg is None:
            return
        if interaction.user != self.member:
            await interaction.response.send_message("You do not have permissions to press that button!", ephemeral=True)
            return
        await self.msg.edit(content=f"Timing out cancelled", view=None)
        self.msg = None
        self.stop()

    async def on_timeout(self):
        if self.msg is None:
            return
        await self.msg.edit(content=f"Timeout menu timed out, how ironic", view=None)
        self.stop()


class TimeoutSelf(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command(rest_is_raw=True)
    async def timeoutself(self, ctx: commands.Context, how_long: str):
        """Times you out for given time. Format example: `5d 3h 4m 2s`."""
        target: discord.Member
        extra = ""
        if isinstance(ctx.author, discord.Member):
            target = ctx.author
        else:
            valid_members = []
            for guild in ctx.bot.guilds:
                maybe_member = guild.get_member(ctx.author.id)
                if maybe_member and guild.me.guild_permissions.moderate_members:
                    valid_members.append(maybe_member)
            if len(valid_members) == 0:
                await ctx.reply("You aren't in any servers where you can be timed out")
                return
            elif len(valid_members) > 1:
                servers = ", ".join(mem.guild.name for mem in valid_members)
                await ctx.reply(f"You are in more than one server ({servers}) where you can be timed out. Post this command in the target server instead")
                return
            else:
                target = valid_members[0]
                extra = f" in server {target.guild.name}"
        time = parse_simple_time_interval(how_long)
        if time.total_seconds() <= 0:
            await ctx.reply("Incorrect time interval specification. You want something like `3h 5m 2s`.")
            return
        if time > datetime.timedelta(days=28):
            await ctx.reply("Discord doesn't allow timeouts longer than 28 days.")
            return
        if time > datetime.timedelta(hours=1):
            timestamp = int((datetime.datetime.now() + time).timestamp())
            view = TimeoutConfirm(time, target)
            view.msg = await ctx.reply(f"Are you sure you want to be timed out approximately until <t:{timestamp}:F> (<t:{timestamp}:R>){extra}? You cannot undo this.", view=view)
            return
        try:
            await target.timeout(time, reason="self-requested via command")
        except discord.Forbidden:
            await ctx.reply("Missing permissions")
            return
        timestamp = int((datetime.datetime.now() + time).timestamp())
        await ctx.reply(f"Timed out until <t:{timestamp}:F> (<t:{timestamp}:R>){extra}")
