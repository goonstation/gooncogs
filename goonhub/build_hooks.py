import random
import asyncio
import discord
import datetime
from fastapi import FastAPI
from redbot.core.data_manager import bundled_data_path
from pydantic import BaseModel
from typing import *
from .utilities import random_emoji
import logging

class BuildFinishedModel(BaseModel):
    api_key: str
    last_compile: Optional[str]
    branch: Optional[str]
    author: Optional[str]
    message: Optional[str]
    commit: Optional[str]
    server: str
    cancelled: Optional[bool]
    error: Union[bool,str]
    mapSwitch: Optional[int]
    mergeConflicts: Optional[list[dict]]

class BuildHooks():
    def __init__(self, config, Goonhub, app: FastAPI):
        self.config = config
        self.Goonhub = Goonhub
        self.app = app
        self.rnd = random.Random()
        self.funny_messages = open(
            bundled_data_path(self.Goonhub) / "code_quality.txt"
        ).readlines()
        self.processed_successful_commits = {}
        self.processed_failed_commits = set()
        self.build_finished_lock = asyncio.Lock()

        @app.post("/wireci/build_finished")
        async def build_finished(data: BuildFinishedModel):
            success = not bool(data.error)
            clean_success = success and not data.mergeConflicts
            channels = await self.config.channels()
            if not len(channels): return
            data.server = data.server.strip()
            goonservers = self.Goonhub.bot.get_cog("GoonServers")
            server = goonservers.resolve_server(data.server)
            if data.message is None:
                error_message = data.error
                if error_message == True:
                    error_message = "unknown error"
                message = f"**ERROR**: {server.short_name}\n```\n{error_message}\n```"
                for channel_id in channels:
                    channel = self.Goonhub.bot.get_channel(int(channel_id))
                    msg = await channel.send(message)
                return
            data.last_compile = data.last_compile.strip()
            data.branch = data.branch.strip()
            data.author = data.author.strip()
            data.message = data.message.strip()
            data.commit = data.commit.strip()
            repo = await self.Goonhub.config.repo()
            message = ""
            embed = None
            
            if data.cancelled:
                commit_message = data.message
                if "\n" in commit_message:
                    commit_message = commit_message.split("\n")[0]
                message = f"**CANCELLED** __{data.branch}__ on {server.short_name} \N{cross mark} `{data.commit[:7]}` by {data.author}: `{commit_message}`"
                success = False
            elif clean_success:
                commit_message = data.message
                if "\n" in commit_message:
                    commit_message = commit_message.split("\n")[0]
                guild = self.Goonhub.bot.get_channel(int(next(iter(channels)))).guild
                message_start = f"__{data.branch}__ on "
                message_end = f"{server.short_name} \N{white heavy check mark} `{data.commit[:7]}` by {data.author}: `{commit_message}`"
                message = message_start + message_end
                if data.commit not in self.processed_successful_commits:
                    message += f"\nCode quality: {await self.funny_message(data.commit, guild)}"
                elif all(
                    msg.channel.last_message_id == msg.id
                    for msg in self.processed_successful_commits[data.commit]
                ):
                    new_processed_commits = []
                    for msg in self.processed_successful_commits[data.commit]:
                        first_part, second_part = msg.content.split(
                            "\N{WHITE HEAVY CHECK MARK}"
                        )
                        message = (
                            first_part[:-1]
                            + ", "
                            + server.short_name
                            + " \N{WHITE HEAVY CHECK MARK}"
                            + second_part
                        )
                        new_processed_commits.append(await msg.edit(content=message))
                    self.processed_successful_commits[data.commit] = new_processed_commits
                    return
            else:
                embed = discord.Embed()
                embed.title = f"`{data.branch}` on {server.short_name}: " + (
                    "succeeded" if success else "failed"
                )
                embed.colour = (
                    discord.Colour.from_rgb(60, 100, 45)
                    if success
                    else discord.Colour.from_rgb(150, 60, 45)
                )
                embed.description = f"```\n{data.last_compile}\n```"
                if not success:
                    if data.error == True:
                        pass
                    elif "\n" in error_message.strip():
                        embed.description += f"\nError:\n```{data.error}```"
                    else:
                        embed.description += f"\nError: `{data.error.strip()}`"
                embed.timestamp = datetime.datetime.utcnow()
                embed.set_image(
                    url=f"https://opengraph.githubassets.com/1/{repo}/commit/{data.commit}"
                )
                embed.add_field(
                    name="commit",
                    value=f"[{data.commit[:7]}](https://github.com/{repo}/commit/{data.commit})",
                )
                embed.add_field(name="message", value=data.message)
                embed.add_field(name="author", value=data.author)
                if len(data.mergeConflicts) != 0:
                    merge_conflict_text = "\n".join(f" - [{c['prId']}](https://github.com/{repo}/pull/{c['prId']}): {c['files']}" for c in data.mergeConflicts)
                    embed.add_field(name="merge conflicts", value=merge_conflict_text)
                embed.set_footer(
                    text="Code quality: " + await self.funny_message(data.commit)
                )
                if not success and data.commit not in self.processed_failed_commits:
                    author_discord_id = None
                    githubendpoint = self.Goonhub.bot.get_cog("GithubEndpoint")
                    if githubendpoint:
                        author_discord_id = await githubendpoint.config.custom(
                            "contributors", data.author
                        ).discord_id()
                    if author_discord_id is not None:
                        message = self.Goonhub.bot.get_user(author_discord_id).mention
                        
            succ_messages = []
            if success:
                self.processed_successful_commits[data.commit] = succ_messages
            else:
                self.processed_failed_commits.add(data.commit)
            for channel_id in channels:
                channel = self.Goonhub.bot.get_channel(int(channel_id))
                msg = None
                if embed:
                    msg = await channel.send(message, embed=embed)
                else:
                    msg = await channel.send(message)
                if success:
                    succ_messages.append(msg)
    
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
            githubendpoint = self.Goonhub.bot.get_cog("GithubEndpoint")
            if githubendpoint:
                person = self.rnd.choice(
                    list(
                        (
                            await githubendpoint.config.custom("contributors").all()
                        ).keys()
                    )
                )
                return self.rnd.choice(
                    [
                        f"Like a thing {person} wrote",
                        f"{person}-approved",
                    ]
                )
        return self.rnd.choice(self.funny_messages).strip()