import discord
from redbot.core import commands
from redbot.core.bot import Red

class NoRoleNoInvite(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or self.bot.user == message.author:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        valid_user = isinstance(message.author, discord.Member) and not message.author.bot
        if not valid_user:
            return

        if message.guild is None or \
            await self.bot.cog_disabled_in_guild(self, message.guild) or \
            not hasattr(message.author, "roles"):
            return

        if len(message.author.roles) <= 1 and "discord.gg" in message.content:
            await message.delete()

