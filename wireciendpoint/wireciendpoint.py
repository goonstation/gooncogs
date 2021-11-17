import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, Config, checks
from redbot.core.data_manager import cog_data_path, bundled_data_path
import discord.errors
from redbot.core.bot import Red
from typing import *
from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import re
import time
import functools
import inspect
from redbot.core.utils.chat_formatting import pagify
import collections
from pydantic import BaseModel
import datetime
import random
from bisect import bisect
from itertools import accumulate
import aiohttp

EMOJI_RANGES_UNICODE = {
    6: [
        ('\U0001F300', '\U0001F320'),
        ('\U0001F330', '\U0001F335'),
        ('\U0001F337', '\U0001F37C'),
        ('\U0001F380', '\U0001F393'),
        ('\U0001F3A0', '\U0001F3C4'),
        ('\U0001F3C6', '\U0001F3CA'),
        ('\U0001F3E0', '\U0001F3F0'),
        ('\U0001F400', '\U0001F43E'),
        ('\U0001F440', ),
        ('\U0001F442', '\U0001F4F7'),
        ('\U0001F4F9', '\U0001F4FC'),
        ('\U0001F500', '\U0001F53C'),
        ('\U0001F540', '\U0001F543'),
        ('\U0001F550', '\U0001F567'),
        ('\U0001F5FB', '\U0001F5FF')
    ],
    7: [
        ('\U0001F300', '\U0001F32C'),
        ('\U0001F330', '\U0001F37D'),
        ('\U0001F380', '\U0001F3CE'),
        ('\U0001F3D4', '\U0001F3F7'),
        ('\U0001F400', '\U0001F4FE'),
        ('\U0001F500', '\U0001F54A'),
        ('\U0001F550', '\U0001F579'),
        ('\U0001F57B', '\U0001F5A3'),
        ('\U0001F5A5', '\U0001F5FF')
    ],
    8: [
        ('\U0001F300', '\U0001F579'),
        ('\U0001F57B', '\U0001F5A3'),
        ('\U0001F5A5', '\U0001F5FF')
    ]
}

def random_emoji(unicode_version = 8, rnd = random):
    if unicode_version in EMOJI_RANGES_UNICODE:
        emoji_ranges = EMOJI_RANGES_UNICODE[unicode_version]
    else:
        emoji_ranges = EMOJI_RANGES_UNICODE[-1]

    # Weighted distribution
    count = [ord(r[-1]) - ord(r[0]) + 1 for r in emoji_ranges]
    weight_distr = list(accumulate(count))

    # Get one point in the multiple ranges
    point = rnd.randrange(weight_distr[-1])

    # Select the correct range
    emoji_range_idx = bisect(weight_distr, point)
    emoji_range = emoji_ranges[emoji_range_idx]

    # Calculate the index in the selected range
    point_in_range = point
    if emoji_range_idx != 0:
        point_in_range = point - weight_distr[emoji_range_idx - 1]

    # Emoji 😄
    emoji = chr(ord(emoji_range[0]) + point_in_range)
    emoji_codepoint = "U+{}".format(hex(ord(emoji))[2:].upper())

    return (emoji, emoji_codepoint)


class WireCiEndpoint(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 1482189223515)
        self.config.register_global(channels={}, repo=None)
        self.rnd = random.Random()
        self.funny_messages = open(bundled_data_path(self) / "code_quality.txt").readlines()
        self.session = aiohttp.ClientSession()
        self.processed_successful_commits = set()
        self.processed_failed_commits = set()

    def cog_unload(self):
        asyncio.create_task(self.session.cancel())

    def register_to_general_api(self, app):
        class BuildFinishedModel(BaseModel):
            api_key: str
            last_compile: str
            branch: str
            author: str
            message: str
            commit: str
            server: str
            error: Optional[str]

        @app.post("/wireci/build_finished")
        async def build_finished(data: BuildFinishedModel):
            if data.api_key != (await self.bot.get_shared_api_tokens('wireciendpoint'))['incoming_api_key']:
                return 
            success = data.error is None
            channels = await self.config.channels()
            if not len(channels):
                return
            data.last_compile = data.last_compile.strip()
            data.branch = data.branch.strip()
            data.author = data.author.strip()
            data.message = data.message.strip()
            data.commit = data.commit.strip()
            data.server = data.server.strip()
            repo = await self.config.repo()
            message = ""
            embed = None
            goonservers = self.bot.get_cog('GoonServers')
            server = goonservers.resolve_server(data.server)
            if success:
                commit_message = data.message
                if '\n' in commit_message:
                    commit_message = commit_message.split('\n')[0]
                guild = self.bot.get_channel(int(next(iter(channels)))).guild
                message = f"__{data.branch}__ on {server.short_name} \N{white heavy check mark} `{data.commit[:7]}` by {data.author}: `{commit_message}`"
                if data.commit not in self.processed_successful_commits:
                    message += f"\nCode quality: {await self.funny_message(data.commit, guild)}"
            else:
                embed = discord.Embed()
                embed.title = f"`{data.branch}` on {server.short_name}: " + ("succeeded" if success else "failed")
                embed.colour = discord.Colour.from_rgb(60, 100, 45) if success else discord.Colour.from_rgb(150, 60, 45)
                embed.description = f"```\n{data.last_compile}\n```"
                if not success:
                    error_message = data.error
                    if error_message.lower() == "true":
                        pass
                    elif '\n' in error_message.strip():
                        embed.description += f"\nError:\n```{error_message}```"
                    else:
                        embed.description += f"\nError: `{error_message.strip()}`"
                embed.timestamp = datetime.datetime.utcnow()
                embed.set_image(url=f"https://opengraph.githubassets.com/1/{repo}/commit/{data.commit}")
                embed.add_field(name="commit", value=f"[{data.commit[:7]}](https://github.com/{repo}/commit/{data.commit})")
                embed.add_field(name="message", value=data.message)
                embed.add_field(name="author", value=data.author)
                embed.set_footer(text="Code quality: " + await self.funny_message(data.commit))
                if not success and data.commit not in self.processed_failed_commits:
                    author_discord_id = None
                    githubendpoint = self.bot.get_cog("GithubEndpoint")
                    if githubendpoint:
                        author_discord_id = await githubendpoint.config.custom("contributors", data.author).discord_id()
                    if author_discord_id is not None:
                        message = self.bot.get_user(author_discord_id).mention
            if success:
                self.processed_successful_commits.add(data.commit)
            else:
                self.processed_failed_commits.add(data.commit)
            for channel_id in channels:
                channel = self.bot.get_channel(int(channel_id))
                if embed:
                    await channel.send(message, embed=embed)
                else:
                    await channel.send(message)

    async def funny_message(self, seed, guild=None):
        self.rnd.seed(seed)
        if self.rnd.randint(1, 30) == 1:
            if guild and self.rnd.randint(1, 2) == 1:
                return str(self.rnd.choice(guild.emojis))
            else:
                return random_emoji(rnd=self.rnd)[0]
        if self.rnd.randint(1, 1 + len(self.funny_messages)) == 1:
            return "Rolling a d20 for a quality check: " + str(self.rnd.randint(1, 20))
        if self.rnd.randint(1, 2 + len(self.funny_messages)) <= 2:
            githubendpoint = self.bot.get_cog("GithubEndpoint")
            if githubendpoint:
                person = self.rnd.choice(list((await githubendpoint.config.custom("contributors").all()).keys()))
                return self.rnd.choice([
                    f"Like a thing {person} wrote",
                    f"{person}-approved",
                    ])
        return self.rnd.choice(self.funny_messages).strip()

    @commands.group(name="ci")
    @checks.admin()
    async def wireciendpoint(self, ctx: commands.Context):
        """Manage Wire's CI system."""
        pass

    @wireciendpoint.command(aliases=["check"])
    async def status(self, ctx: commands.Context):
        """Check status of CI builds."""
        tokens = await self.bot.get_shared_api_tokens('wireciendpoint')
        url = tokens.get('api_path') + '/status'
        api_key = tokens.get('outgoing_api_key')
        async with self.session.get(
                url,
                headers = {
                    'Api-Key': api_key,
                    },
                ) as res:
            if res.status != 200:
                for page in pagify(f"Server responded with an error code {res.status}: `{await res.text()}`"):
                    await ctx.send(page)
                return
            data = await res.json(content_type=None)
            goonservers = self.bot.get_cog("GoonServers")
            message = [f"Max compile jobs: {data.get('maxCompileJobs', 'N/A')}"]
            current_jobs = data.get('currentCompileJobs', [])
            if not current_jobs:
                message.append("No jobs currently running")
            else:
                message.append(f"Currently compiling: " + ", ".join(goonservers.resolve_server(sid).short_name for sid in current_jobs))
            queued_jobs = data.get('queuedJobs', [])
            if not queued_jobs:
                message.append("No jobs queued")
            else:
                message.append(f"Queued: " + ", ".join(goonservers.resolve_server(sid).short_name for sid in queued_jobs))
            await ctx.send('\n'.join(message))

    @wireciendpoint.command()
    async def build(self, ctx: commands.Context, server_name: str):
        """Start a CI build."""
        tokens = await self.bot.get_shared_api_tokens('wireciendpoint')
        url = tokens.get('api_path') + '/build'
        api_key = tokens.get('outgoing_api_key')
        goonservers = self.bot.get_cog("GoonServers")
        servers = goonservers.resolve_server_or_category(server_name)
        if not servers:
            await ctx.send("Unknown server.")
            return
        success = True
        for server in servers:
            server_id = server.tgs
            async with self.session.post(
                    url,
                    headers = {
                        'Api-Key': api_key,
                        },
                    json = {'server': server_id}
                    ) as res:
                if res.status != 200:
                    for page in pagify(f"Server responded with an error code {res.status}: `{await res.text()}`"):
                        await ctx.send(page)
                    continue
                data = await res.json(content_type=None)
                if not data.get("success"):
                    await ctx.send(f"Idk what happened: `{await res.text()}`")
                    success = False
        if success:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @wireciendpoint.command()
    async def addchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Subscribe a channel to receive CI build updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            channels[str(channel.id)] = None
        await ctx.send(f"Channel {channel.mention} will now receive notifications about builds.")

    @wireciendpoint.command()
    async def setrepo(self, ctx: commands.Context, repo: str):
        """Set GitHub repo for commit link purposes."""
        await self.config.repo.set(repo)
        await ctx.send(f"Repo set to `{repo}`.")

    @wireciendpoint.command()
    async def removechannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Unsubscribe a channel from CI build updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            del channels[str(channel.id)]
        await ctx.send(f"Channel {channel.mention} will no longer receive notifications about builds.")

    @wireciendpoint.command()
    async def checkchannels(self, ctx: commands.Context):
        """Check channels subscribed to CI build updates."""
        channel_ids = await self.config.channels()
        if not channel_ids:
            await ctx.send("No channels.")
        else:
            await ctx.send("\n".join(self.bot.get_channel(int(ch)).mention for ch in channel_ids))

