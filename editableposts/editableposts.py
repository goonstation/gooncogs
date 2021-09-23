import asyncio
import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from copy import copy
import re
from typing import Optional, Union
from redbot.core.utils.chat_formatting import pagify

class EditablePosts(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=85215643217426)
        self.config.init_custom("editable_posts", 1)
        self.config.register_custom("editable_posts", editable=False)
        self.config.register_custom("editable_posts", channel=None)

    @commands.group()
    @checks.admin()
    async def editable_posts(self, ctx: commands.Context):
        """Group command for creating posts you can edit later."""
        pass

    async def valid_message(self, message: discord.Message):
        msg_id = message.id
        return await self.config.custom("editable_posts", msg_id).editable()
    
    @editable_posts.command()
    @checks.admin()
    async def create(self, ctx: commands.Context, channel: discord.TextChannel, *, title: Optional[str]):
        embed = discord.Embed(title=title or "[reserved post]", color=await ctx.embed_color())
        msg = await channel.send(embed=embed)
        await self.config.custom("editable_posts", msg.id).editable.set(True)
        await self.config.custom("editable_posts", msg.id).channel.set(msg.channel.id)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @editable_posts.command()
    @checks.admin()
    async def title(self, ctx: commands.Context, message: discord.Message, *, title: str):
        if not await self.valid_message(message):
            return
        embed = message.embeds[0]
        embed.title = title
        await message.edit(embed=embed)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @editable_posts.command()
    @checks.admin()
    async def edit(self, ctx: commands.Context, message: discord.Message, *, text: str):
        if not await self.valid_message(message):
            return
        embed = message.embeds[0]
        embed.description = text
        await message.edit(embed=embed)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @editable_posts.command()
    @checks.admin()
    async def remove(self, ctx: commands.Context, message: discord.Message):
        if not await self.valid_message(message):
            return
        await message.delete()
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @editable_posts.command()
    @checks.admin()
    async def list(self, ctx: commands.Context):
        messages = []
        for msg_id, data in (await self.config.custom("editable_posts").all()).items():
            channel = self.bot.get_channel(data['channel'])
            if channel.guild != ctx.guild or not data['editable']:
                continue
            message = None
            try:
                message = await channel.fetch_message(msg_id)
            except discord.errors.NotFound:
                await self.config.custom("editable_posts", msg_id).editable.set(False)
                continue
            messages.append(message)
        out = ""
        for message in messages:
            msg_text = message.embeds[0].title + " " + message.jump_url
            if len(msg_text) + 1 + len(out) >= 2048:
                await ctx.send(out)
                out = ""
            out += ("" if not out else "\n") + msg_text
        if out:
            for page in pagify(out):
                await ctx.send(page)

