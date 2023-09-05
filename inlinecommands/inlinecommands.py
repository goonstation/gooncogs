import asyncio
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from copy import copy
import re


class InlineCommands(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    async def _handle_alias(self, message: discord.Message, command: str, prefix: str):
        alias_cog = self.bot.get_cog("Alias")
        if not alias_cog:
            return None
        potential_alias = command.split(" ")[0]
        msg = copy(message)
        msg.content = prefix + command
        # accessing private variables, sue me!
        alias = await alias_cog._aliases.get_alias(message.guild, potential_alias)
        if alias:
            return alias_cog.call_alias(msg, prefix, alias)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        tasks = []
        for command in re.findall(r"\[(.*?)\]", message.content):
            if not command:
                continue
            prefix = await self.bot.get_prefix(message)
            if isinstance(prefix, list):
                prefix = prefix[0]
            msg = copy(message)
            msg.content = prefix + command
            new_ctx = await self.bot.get_context(msg)
            tasks.append(self.bot.invoke(new_ctx))

            alias_task = await self._handle_alias(message, command, prefix)
            if alias_task:
                tasks.append(alias_task)

        await asyncio.gather(*tasks, return_exceptions=True)
