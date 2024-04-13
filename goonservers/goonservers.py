import asyncio
import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import pagify
import discord.errors
from redbot.core.bot import Red
from typing import *
import socket
import re
import datetime
import random
from collections import OrderedDict
import functools
import json
import aiohttp


class UnknownServerError(Exception):
    pass


class Subtype:
    def __init__(self, name, data, cog):
        self.name = name
        self.channels = {}
        for name, channel_ids in data["channels"].items():
            self.channels[name] = cog.channel_trans(channel_ids)
        self.servers = []

    async def send_to_channel(self, channel, content=None, *args, **kwargs):
        if isinstance(content, str):
            for page in pagify(content):
                await channel.send(content=page, *args, **kwargs)
        else:
            await channel.send(content=content, *args, **kwargs)

    async def channel_broadcast(
        self, bot, channel_type, *args, exception=None, **kwargs
    ):
        tasks = [
            self.send_to_channel(bot.get_channel(ch), *args, **kwargs)
            for ch in self.channels[channel_type]
            if ch != exception
        ]
        await asyncio.gather(*tasks)


class Server:
    def __init__(self, data, cog):
        self.host = data["host"]
        self.port = data["port"]
        self.full_name = data.get("full_name") or Server.host_to_full_name(self.host)
        self.type = data["type"]
        self.subtype = data.get("subtype")
        if self.subtype is not None:
            self.subtype = cog.subtypes[self.subtype]
            self.subtype.servers.append(self)
        self.url = data.get("url")
        self.tgs = data.get("tgs")
        self.short_name = data.get("short_name") or self.full_name
        self.names = data.get("names", [])

    @property
    def connect_url(self):
        if not self.host:
            return None
        url = f"{self.host}:{self.port}"
        if not url.startswith("byond://"):
            url = "byond://" + url
        return url

    @property
    def aliases(self):
        aliases = self.names
        if self.full_name:
            aliases.append(self.full_name)
        if self.short_name:
            aliases.append(self.short_name)
        return [a.lower() for a in aliases]

    @classmethod
    def host_to_full_name(cls, host):
        full_name = re.sub(r"\.[a-z]*$", "", host)  # TLD
        full_name = re.sub(r"ss13|station13|station|hub|play|server", "", full_name)
        full_name = "".join(c if c.isalnum() else " " for c in full_name)
        full_name = re.sub(r" +", " ", full_name)
        words = full_name.split()
        full_name = " ".join(word.capitalize() for word in words)
        return full_name

    @classmethod
    def from_hostport(cls, hostport):
        match = re.match(r"^(?:byond://)?(.*):([0-9]+)$", hostport)
        if not match:
            return None
        host, port = match.groups()
        full_name = Server.host_to_full_name(host)
        server_data = {
            "host": host,
            "port": int(port),
            "full_name": full_name,
            "type": "other",
        }
        return Server(server_data, None)


class GoonServers(commands.Cog):
    INITIAL_CHECK_TIMEOUT = 0.2
    ALLOW_ADHOC = True
    COLOR_GOON = discord.Colour.from_rgb(222, 190, 49)
    COLOR_OTHER = discord.Colour.from_rgb(130, 130, 222)
    COLOR_ERROR = discord.Colour.from_rgb(220, 150, 150)

    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=66217843218752)
        self.config.register_global(servers=[], categories={}, channels={}, subtypes={})

    @functools.lru_cache
    def channel_to_subtypes(self, channel_id, usage):
        return tuple(
            subtype
            for subtype in self.subtypes.values()
            if channel_id in subtype.channels[usage]
        )

    @functools.lru_cache
    def channel_to_servers(self, channel_id, usage):
        result = []
        for subtype in self.channel_to_subtypes(channel_id, usage):
            result.extend(subtype.servers)
        return tuple(result)

    def channel_trans(self, channels):
        if isinstance(channels, int):
            return channels
        if isinstance(channels, str):
            return self.channels[channels]
        return [self.channel_trans(ch) for ch in channels]

    async def reload_config(self):
        self.valid_channels = set()
        self.channels = await self.config.channels()
        self.categories = await self.config.categories()
        self.subtypes = {}
        for subtype_name, subtype_data in (await self.config.subtypes()).items():
            self.subtypes[subtype_name] = Subtype(subtype_name, subtype_data, self)
            for channel_type, channel_ids in self.subtypes[
                subtype_name
            ].channels.items():
                self.valid_channels |= set(channel_ids)
        self.servers = []
        for server_data in await self.config.servers():
            self.servers.append(Server(server_data, self))
        self.aliases = {}
        for server in self.servers:
            for alias in server.aliases:
                if alias in self.aliases and self.aliases[alias] != server:
                    raise ValueError(f"Alias collision on '{alias}'.")
                self.aliases[alias] = server

    def resolve_server(self, name):
        name = name.lower()
        if name in self.aliases:
            return self.aliases[name]
        if self.ALLOW_ADHOC:
            return Server.from_hostport(name)
        return None

    def resolve_server_or_category(self, name):
        name = name.lower()
        single_server = self.resolve_server(name)
        if single_server is not None:
            return [single_server]
        if name not in self.categories:
            return []
        return [self.resolve_server(x) for x in self.categories[name]]

    async def send_to_server(self, server, message, to_dict=False):
        if isinstance(server, str):
            server = self.resolve_server(server)
        if server is None:
            raise UnknownServerError()
        worldtopic = self.bot.get_cog("WorldTopic")
        if not isinstance(message, str):
            if isinstance(message, dict):
                tokens = await self.bot.get_shared_api_tokens("goonservers")
                message["auth"] = tokens.get("auth_token")
            message = worldtopic.iterable_to_params(message)
        result = await worldtopic.send((server.host, server.port), message)
        if to_dict and isinstance(result, str):
            result = worldtopic.params_to_dict(result)
        return result

    async def send_to_server_safe(
        self, server, message, messageable, to_dict=False, react_success=False
    ):
        worldtopic = self.bot.get_cog("WorldTopic")
        error_fn = None
        if hasattr(messageable, "reply"):
            error_fn = messageable.reply
        elif hasattr(messageable, "send"):
            error_fn = messageable.send
        try:
            result = await self.send_to_server(server, message, to_dict=to_dict)
        except UnknownServerError:
            await error_fn("Unknown server.")
        except ConnectionRefusedError:
            await error_fn("Server offline.")
        except ConnectionResetError:
            await error_fn("Server restarting.")
        except asyncio.TimeoutError:
            await error_fn("Server restarting or offline.")
        else:
            if react_success and hasattr(messageable, "add_reaction"):
                await messageable.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            return result
        return None

    async def send_to_servers(self, servers, message, exception=None, to_dict=False):
        if isinstance(servers, str):
            servers = self.resolve_server_or_category(servers)
        servers = [self.resolve_server(s) if isinstance(s, str) else s for s in servers]
        if exception is not None:
            servers = [s for s in servers if s != exception]
        worldtopic = self.bot.get_cog("WorldTopic")
        if not isinstance(message, str):
            message = worldtopic.iterable_to_params(message)
        tasks = [self.send_to_server(s, message) for s in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        if to_dict:
            results = [
                worldtopic.params_to_dict(r) if isinstance(r, str) else r
                for r in results
            ]
        return results

    def seconds_to_hhmmss(self, input_seconds):
        hours, remainder = divmod(input_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))

    def status_format_elapsed(self, status):
        elapsed = (
            status.get("elapsed")
            or status.get("round_duration")
            or status.get("stationtime")
        )
        if elapsed == "pre":
            elapsed = "preround"
        elif elapsed == "post":
            elapsed = "finished"
        elif elapsed is not None:
            try:
                elapsed = self.seconds_to_hhmmss(int(elapsed))
            except ValueError:
                pass
        return elapsed

    async def get_status_info(self, server, worldtopic):
        result = OrderedDict()
        result["full_name"] = server.full_name
        result["url"] = server.url
        result["type"] = server.type
        result["error"] = None
        try:
            response = await worldtopic.send((server.host, server.port), "status")
        except (asyncio.exceptions.TimeoutError, TimeoutError) as e:
            result["error"] = "Server not responding."
            return result
        except (socket.gaierror, ConnectionRefusedError) as e:
            result["error"] = "Unable to connect."
            return result
        except ConnectionResetError:
            result["error"] = "Connection reset by server (possibly just restarted)."
            return result
        if response is None:
            result["error"] = "Invalid server response."
            return result
        status = worldtopic.params_to_dict(response)
        if len(response) < 20 or ("players" in status and len(status["players"]) > 5):
            response = await worldtopic.send((server.host, server.port), "status&format=json")
            status = json.loads(response)
        result["station_name"] = status.get("station_name")
        try:
            result["players"] = int(status["players"]) if "players" in status else None
        except ValueError:
            result["players"] = None
        result["map"] = status.get("map_name")
        result["mode"] = status.get("mode")
        result["time"] = self.status_format_elapsed(status)
        result["shuttle"] = None
        result["shuttle_eta"] = None
        if "shuttle_time" in status and status["shuttle_time"] != "welp":
            shuttle_time = int(status["shuttle_time"])
            if shuttle_time != 360:
                eta = "ETA" if shuttle_time >= 0 else "ETD"
                shuttle_time = abs(shuttle_time)
                result["shuttle"] = self.seconds_to_hhmmss(shuttle_time)
                result["shuttle_eta"] = eta
        return result

    def status_result_parts(self, status_info):
        result_parts = []
        if status_info["station_name"]:
            result_parts.append(status_info["station_name"])
        if status_info["players"] is not None:
            result_parts.append(
                f"{status_info['players']} player"
                + ("s" if status_info["players"] != 1 else "")
            )
        if status_info["map"]:
            result_parts.append(f"map: {status_info['map']}")
        if status_info["mode"] and status_info["mode"] != "secret":
            result_parts.append(f"mode: {status_info['mode']}")
        if status_info["time"]:
            result_parts.append(f"time: {status_info['time']}")
        if status_info["shuttle_eta"]:
            result_parts.append(
                f"shuttle {status_info['shuttle_eta']}: {status_info['shuttle']}"
            )
        return result_parts

    def generate_status_text(self, status_info, embed_url=False):
        result = status_info["full_name"]
        if embed_url and status_info["url"]:
            result = f"[{result}]({status_info['url']})"
        result = f"**{result}** "
        if status_info["error"]:
            return result + status_info["error"]
        result += " | ".join(self.status_result_parts(status_info))
        if not embed_url and status_info["url"]:
            result += " " + status_info["url"]
        return result

    def generate_status_embed(self, status_info, embed=None):
        if embed is None:
            embed = discord.Embed()
        embed.title = status_info["full_name"]
        if status_info["url"]:
            embed.url = status_info["url"]
        if status_info["error"]:
            embed.description = status_info["error"]
            embed.colour = self.COLOR_ERROR
            return embed
        if status_info["type"] == "goon":
            embed.colour = self.COLOR_GOON
        else:
            embed.colour = self.COLOR_OTHER
        embed.description = " | ".join(self.status_result_parts(status_info))
        return embed

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def checkclassic(self, ctx: commands.Context, name: str = "all"):
        """
        Checks the status of a Goonstation server of servers.
        `name` can be either numeric server id, the server's name, a server category like "all" or even server address.
        """

        if name.lower() in self.CHECK_GIMMICKS:
            result = await self.CHECK_GIMMICKS[name.lower()](self, ctx)
            if result:
                await ctx.send(result)
                return

        worldtopic = self.bot.get_cog("WorldTopic")
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        futures = [asyncio.Task(self.get_status_info(s, worldtopic)) for s in servers]
        done, pending = [], futures
        message = None
        async with ctx.typing():
            while pending:
                when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
                done, pending = await asyncio.wait(
                    pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when
                )
                message_text = "\n".join(
                    self.generate_status_text(f.result()) for f in futures if f.done()
                )
                if not done:
                    continue
                if message is None:
                    message = await ctx.send(message_text)
                else:
                    await message.edit(content=message_text)

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def check(self, ctx: commands.Context, name: str = "all"):
        """Checks the status of a Goonstation server of servers.
        `name` can be either numeric server id, the server's name or a server category like "all".
        """
        if (
            isinstance(ctx.channel, discord.TextChannel)
            and not ctx.channel.permissions_for(ctx.channel.guild.me).embed_links
        ):
            return await self.checkclassic(ctx, name)

        embed = discord.Embed()
        embed.colour = self.COLOR_GOON

        if name.lower() in self.CHECK_GIMMICKS:
            result = await self.CHECK_GIMMICKS[name.lower()](self, ctx)
            if result:
                embed.description = result
                await ctx.send(embed=embed)
                return

        worldtopic = self.bot.get_cog("WorldTopic")
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        single_server_embed = len(servers) == 1
        futures = [asyncio.Task(self.get_status_info(s, worldtopic)) for s in servers]
        done, pending = [], futures
        message = None
        all_goon = all(server.type == "goon" for server in servers)
        if not all_goon:
            embed.colour = self.COLOR_OTHER
        async with ctx.typing():
            while pending:
                when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
                done, pending = await asyncio.wait(
                    pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when
                )
                if not single_server_embed:
                    message_text = "\n".join(
                        self.generate_status_text(f.result(), embed_url=True)
                        for f in futures
                        if f.done()
                    )
                    embed.description = message_text
                else:
                    for f in futures:
                        if f.done():
                            embed = self.generate_status_embed(f.result(), embed)
                if not done:
                    continue
                if message is None:
                    message = await ctx.send(embed=embed)
                else:
                    await message.edit(embed=embed)

    async def _check_gimmick_oven(self, ctx: commands.Context):
        ts = int(datetime.datetime.now().timestamp())
        ts += random.randint(1, 60 * 60)
        return f"The cookies will be done <t:{ts}:R>."

    async def _check_gimmick_goonstation(self, ctx: commands.Context):
        return f"Goonstation: dead, sorry, go home."

    async def _check_gimmick_goonhub(self, ctx: commands.Context):
        URL = "https://goonhub.com"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(URL) as response:
                    if response.status < 400:
                        return "https://goonhub.com is online, yay"
        except aiohttp.ClientError:
            pass
        return "https://goonhub.com is offline, oh no"

    CHECK_GIMMICKS = {
        "oven": _check_gimmick_oven,
        "goonstation": _check_gimmick_goonstation,
        "goonhub": _check_gimmick_goonhub,
    }
