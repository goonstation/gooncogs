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


class GithubEndpoint(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 45632487953)
        self.config.init_custom("repos", 1)
        self.config.register_custom("repos", channel_ids={})
        self.config.init_custom("contributors", 1)
        self.config.register_custom("contributors", discord_id=None)

    def register_to_general_api(self, app):
        class WorkflowFailedModel(BaseModel):
            api_key: str
            name: str
            url: str
            branch: str
            author: str
            message: str
            commit: str
            repo: str

        @app.post("/github/workflow_failed")
        async def workflow_failed(data: WorkflowFailedModel):
            if (
                data.api_key
                != (await self.bot.get_shared_api_tokens("githubendpoint"))["api_key"]
            ):
                return
            channels = await self.channels_of_repo(data.repo)
            if not channels:
                raise ValueError(f"Unknown repository {data.repo}")
            embed = discord.Embed()
            embed.title = f"`{data.branch}`: {data.name} failed"
            embed.colour = discord.Colour.from_rgb(225, 60, 45)
            embed.timestamp = datetime.datetime.utcnow()
            embed.url = data.url
            embed.add_field(
                name="commit",
                value=f"[{data.commit[:7]}](https://github.com/{data.repo}/commit/{data.commit})",
            )
            embed.add_field(name="message", value=data.message)
            embed.add_field(name="author", value=data.author)
            message = ""
            author_discord_id = await self.config.custom(
                "contributors", data.author
            ).discord_id()
            if author_discord_id is not None:
                message = self.bot.get_user(author_discord_id).mention
            for channel in channels:
                await channel.send(message, embed=embed)

    async def channels_of_repo(self, repo: str):
        channel_ids = await self.config.custom("repos", repo).channel_ids()
        return [self.bot.get_channel(int(chid)) for chid in channel_ids.keys()]

    @commands.group()
    @checks.admin()
    async def githubendpoint(self, ctx: commands.Context):
        """Manage messages sent from GitHub."""
        pass

    @githubendpoint.command()
    async def registerself(self, ctx: commands.Context, git_name: str):
        await self.config.custom("contributors", git_name).discord_id.set(ctx.author.id)
        await ctx.send(
            f"Your Discord account will now get pings aimed at git committer {git_name}"
        )

    @githubendpoint.command()
    @checks.is_owner()
    async def registerother(
        self, ctx: commands.Context, git_name: str, user: discord.User
    ):
        await self.config.custom("contributors", git_name).discord_id.set(user.id)
        await ctx.send(
            f"{user.name} will now get pings aimed at git committer {git_name}"
        )

    @githubendpoint.command()
    @checks.is_owner()
    async def unregisterother(self, ctx: commands.Context, git_name: str):
        await self.config.custom("contributors", git_name).discord_id.set(None)
        await ctx.send(f"Unregistered the Discord account linked to {git_name}")

    @githubendpoint.command()
    async def addchannel(
        self, ctx: commands.Context, repo: str, channel: Optional[discord.TextChannel]
    ):
        if channel is None:
            channel = ctx.channel
        async with self.config.custom("repos", repo).channel_ids() as channel_ids:
            channel_ids[str(channel.id)] = None
        await ctx.send(
            f"Channel {channel.mention} will now receive notifications from `{repo}`."
        )

    @githubendpoint.command()
    async def removechannel(
        self, ctx: commands.Context, repo: str, channel: Optional[discord.TextChannel]
    ):
        if channel is None:
            channel = ctx.channel
        async with self.config.custom("repos", repo).channel_ids() as channel_ids:
            del channel_ids[str(channel.id)]
        await ctx.send(
            f"Channel {channel.mention} will no longer receive notifications from `{repo}`."
        )

    @githubendpoint.command()
    async def checkchannels(self, ctx: commands.Context, repo: str):
        channel_ids = await self.config.custom("repos", repo).channel_ids()
        if not channel_ids:
            await ctx.send("No channels.")
        else:
            await ctx.send(
                "\n".join(ch.mention for ch in await self.channels_of_repo(repo))
            )
