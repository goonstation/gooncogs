import asyncio
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from copy import copy
import re

class InlineCommands(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.guild is None or self.bot.user == message.author:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        valid_user = isinstance(message.author, discord.Member) and not message.author.bot
        if not valid_user:
            return

        tasks = []
        # TODO: aliases
        for command in re.findall(r"\[(.*?)\]", message.content):
            prefix = await self.bot.get_prefix(message)
            if isinstance(prefix, list):
                prefix = prefix[0]
            msg = copy(message)
            msg.content = prefix + command
            new_ctx = await self.bot.get_context(msg)
            tasks.append(self.bot.invoke(new_ctx))
        await asyncio.gather(*tasks, return_exceptions=True)

