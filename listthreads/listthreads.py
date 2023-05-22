import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.utils.chat_formatting import pagify
from redbot.core.bot import Red
from typing import *
from collections import OrderedDict

class ListThreads(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def listthreads(self, ctx: commands.Context):
        """
        Lists non-archived threads you have access to.

        Use the `[p]listthreads detailed` subcommand for more details.
        Use the `[p]listthreads all` subcommand too see archived threads too
        Use the `[p]listthreads alldetailed` subcommand for both
        """
        if not isinstance(ctx.author, discord.Member):
            return await ctx.reply("Threads can only exist in servers")
        await self._listthreads(ctx, ctx.author)

    @listthreads.command()
    async def detailed(self, ctx: commands.Context):
        """
        Lists non-archived threads you have access to and gives you a bunch of details.

        \N{derelict house building} = archived
        \N{lock} = locked
        \N{sleuth or spy} = private
        """
        if not isinstance(ctx.author, discord.Member):
            return await ctx.reply("Threads can only exist in servers")
        await self._listthreads(ctx, ctx.author, detailed=True)

    @commands.cooldown(1, 60)
    @listthreads.command()
    async def alldetailed(self, ctx: commands.Context):
        """
        Lists threads (including archived) you have access to and gives you a bunch of details.
        This will take a good while and might require permissions!

        \N{derelict house building} = archived
        \N{lock} = locked
        \N{sleuth or spy} = private
        """
        if not isinstance(ctx.author, discord.Member):
            return await ctx.reply("Threads can only exist in servers")
        async with ctx.typing():
            await self._listthreads(ctx, ctx.author, detailed=True, include_archived=True, with_names=True)

    @commands.cooldown(1, 60)
    @listthreads.command()
    async def all(self, ctx: commands.Context):
        """
        Lists non-archived threads you have access to.

        This will take a good while and might require permissions!
        """
        if not isinstance(ctx.author, discord.Member):
            return await ctx.reply("Threads can only exist in servers")
        async with ctx.typing():
            await self._listthreads(ctx, ctx.author,  include_archived=True, with_names=True)

    async def _listthreads(self, ctx: commands.Context, member: discord.Member, detailed: bool = False, include_archived = False, with_names = False):
        threads = OrderedDict()
        guild = member.guild
        error_channels = []
        for channel in guild.channels:
            found_threads = []
            if isinstance(channel, discord.TextChannel) and channel.permissions_for(member).send_messages_in_threads:
                async def process_thread(thread):
                    if thread.is_private() and not thread.permissions_for(member).manage_threads:
                        try:
                            await thread.fetch_member(member.id)
                        except discord.NotFound:
                            return                            
                    found_threads.append(thread)
                try:
                    for thread in channel.threads:
                        await process_thread(thread)
                except discord.Forbidden:
                    error_channels.append(channel)
                    continue
                if include_archived:
                    try:
                        async for thread in channel.archived_threads():
                            await process_thread(thread)
                    except discord.Forbidden:
                        error_channels.append(channel)
            if len(found_threads) > 0:
                threads[channel] = found_threads
        message_lines = []
        for channel, ch_threads in threads.items():
            message_lines.append(f"{channel.mention}")
            for thread in ch_threads:
                thread_line = f"- {thread.name if with_names else ''}{thread.mention}"
                if detailed:
                    if thread.archived: thread_line += "\N{derelict house building}"
                    if thread.locked: thread_line += "\N{lock}"
                    if thread.is_private(): thread_line += "\N{sleuth or spy}"
                    thread_line += f" {thread.message_count} msgs"
                    thread_line += f", {thread.member_count} users"
                message_lines.append(thread_line)
        message = "\n".join(message_lines)
        if len(error_channels) > 0:
            message += "\n\nInvalid permissions to access these channels:\n" + "\n".join(channel.mention for channel in error_channels)
        for page in pagify(message):
            await ctx.send(page)
