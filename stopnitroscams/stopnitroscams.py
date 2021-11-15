import discord
from redbot.core import commands
from redbot.core.bot import Red

class StopNitroScams(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.sus_messages = {}

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

        key = message.author.id
        if not message.author.guild_permissions.attach_files and "http" in message.content and "free nitro" in message.content.lower():
            self.sus_messages[key] = self.sus_messages.get(key, []) + [message]
            msgs = self.sus_messages[key]
            if len(msgs) >= 3:
                for message in msgs:
                    await message.delete()
                await message.author.ban(reason="free nitro scam", delete_message_days=0)
        else:
            if key in self.sus_messages:
                del self.sus_messages[key]

