import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import re
import time
import functools
import inspect
import collections
from pydantic import BaseModel
import datetime

class WireCiEndpoint(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 1482189223515)
        self.config.register_global(channels={}, repo=None)

    def register_to_general_api(self, app):
        class BuildFinishedModel(BaseModel):
            api_key: str
            last_compile: str
            branch: str
            author: str
            message: str
            commit: str
            error: Optional[str]

        @app.post("/wireci/build_finished")
        async def build_finished(data: BuildFinishedModel):
            if data.api_key != (await self.bot.get_shared_api_tokens('wireciendpoint'))['api_key']:
                return 
            success = data.error is None
            channels = await self.config.channels()
            repo = await self.config.repo()
            embed = discord.Embed()
            embed.title = f"`{data.branch}`: " + ("succeeded" if success else "failed")
            embed.colour = discord.Colour.from_rgb(60, 225, 45) if success else discord.Colour.from_rgb(225, 60, 45)
            embed.description = f"```\n{data.last_compile}\n```"
            if not success:
                error_message = data.error
                if '\n' in error_message.strip():
                    embed.description += f"\nError:\n```{error_message}```"
                else:
                    embed.description += f"\nError: `{error_message.strip()}`"
            embed.timestamp = datetime.datetime.utcnow()
            embed.set_image(url=f"https://opengraph.githubassets.com/1/{repo}/commit/{data.commit}")
            embed.add_field(name="commit", value=f"[{data.commit[:7]}](https://github.com/{repo}/commit/{data.commit})")
            embed.add_field(name="message", value=data.message)
            embed.add_field(name="author", value=data.author)
            message = ""
            if not success:
                author_discord_id = None
                githubendpoint = self.bot.get_cog("GithubEndpoint")
                if githubendpoint:
                    author_discord_id = await githubendpoint.config.custom("contributors", data.author).discord_id()
                if author_discord_id is not None:
                    message = self.bot.get_user(author_discord_id).mention
            for channel_id in channels:
                channel = self.bot.get_channel(int(channel_id))
                await channel.send(message, embed=embed)

    @commands.group()
    @checks.admin()
    async def wireciendpoint(self, ctx: commands.Context):
        """Manage messages sent from GitHub."""
        pass

    @wireciendpoint.command()
    async def addchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            channels[str(channel.id)] = None
        await ctx.send(f"Channel {channel.mention} will now receive notifications about builds.")

    @wireciendpoint.command()
    async def setrepo(self, ctx: commands.Context, repo: str):
        await self.config.repo.set(repo)
        await ctx.send(f"Repo set to `{repo}`.")

    @wireciendpoint.command()
    async def removechannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            del channels[str(channel.id)]
        await ctx.send(f"Channel {channel.mention} will no longer receive notifications about builds.")

    @wireciendpoint.command()
    async def checkchannels(self, ctx: commands.Context):
        channel_ids = await self.config.channels()
        if not channel_ids:
            await ctx.send("No channels.")
        else:
            await ctx.send("\n".join(self.bot.get_channel(int(ch)).mention for ch in channel_ids))

