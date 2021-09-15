import asyncio
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import socket
import re

class GoonServers(commands.Cog):
    INITIAL_CHECK_TIMEOUT = 0.2
    ALLOW_ADHOC = True

    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=66217843218752)
        self.config.register_global(
                servers=[],
                categories={}
            )

    async def reload_config(self):
        self.categories = await self.config.categories()
        self.servers = await self.config.servers()
        self.aliases = {}
        for server in self.servers:
            for name in server['names']:
                self.aliases[name.lower()] = server

    def host_to_full_name(self, host):
        full_name = re.sub(r"\.[a-z]*$", "", host) # TLD
        full_name = re.sub(r"ss13|station13|station|hub|play|server", "", full_name)
        full_name = ''.join(c if c.isalnum() else ' ' for c in full_name)
        full_name = re.sub(r" +", " ", full_name)
        words = full_name.split()
        full_name = ' '.join(word.capitalize() for word in words)
        return full_name

    def resolve_server(self, name):
        name = name.lower()
        if name in self.aliases:
            return self.aliases[name]
        if self.ALLOW_ADHOC:
            match = re.match(r"(?:byond://)?(.*):([0-9]*)", name)
            if match:
                host, port = match.groups()
                full_name = self.host_to_full_name(host)
                return {
                        'host': host,
                        'port': int(port),
                        'full_name': full_name,
                        'type': 'other'
                    }
        return None

    def resolve_server_or_category(self, name):
        single_server = self.resolve_server(name)
        if single_server is not None:
            return [single_server]
        if name.lower() not in self.categories:
            return []
        return [self.resolve_server(x) for x in self.categories[name]]

    def seconds_to_hhmmss(self, input_seconds):
        hours, remainder = divmod(input_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

    def status_format_elapsed(self, status, skip_elapsed=False):
        elapsed = status.get('elapsed') or status.get('round_duration') or status.get('stationtime')
        if elapsed == 'pre':
            elapsed = "preround"
        elif elapsed == 'post':
            elapsed = "finished"
        elif elapsed is not None:
            try:
                elapsed = self.seconds_to_hhmmss(int(float(elapsed))) + ("" if skip_elapsed else " elapsed")
            except ValueError:
                pass
        return elapsed

    async def get_status_text(self, server, worldtopic, embed_url=False):
        result = f"**{server['full_name']}**"
        if embed_url and 'url' in server and server['url']:
            result = f"[{result}]({server['url']})"
        result += " "
        try:
            response = await worldtopic.send((server['host'], server['port']), 'status')
        except (asyncio.exceptions.TimeoutError, TimeoutError) as e:
            return result + "Server not responding"
        except (socket.gaierror, ConnectionRefusedError) as e:
            return result + "Unable to connect."
        status = worldtopic.params_to_dict(response)
        if 'station_name' in status:
            result += f"{status['station_name'] or ''} | "
        players = int(status['players']) if 'players' in status else None
        if players is not None:
            players_plural = 's' if players != 1 else ''
            result += f"{status['players']} player{players_plural}"
        if 'map_name' in status:
            result += f" | map: {status['map_name']}"
        if 'mode' in status and status['mode'] != 'secret':
            result += f" | mode: {status['mode']}"
        elapsed = self.status_format_elapsed(status)
        if elapsed is not None:
            result += f" | {elapsed}"
        if 'shuttle_time' in status and status['shuttle_time'] != 'welp':
            shuttle_time = int(float(status['shuttle_time']))
            if shuttle_time != 360:
                eta = 'ETA' if shuttle_time >= 0 else 'ETD'
                shuttle_time = abs(shuttle_time)
                result += f" | {self.seconds_to_hhmmss(shuttle_time)} shuttle {eta}"
        if not embed_url and 'url' in server and server['url']:
            result += f" {server['url']}"
        return result

    async def get_status_embed(self, server, worldtopic):
        embed = discord.Embed(type='article')
        embed.colour = discord.Colour.from_rgb(220, 150, 150)
        embed.title = server['full_name']
        if 'url' in server and server['url']:
            embed.url = server['url']
        try:
            response = await worldtopic.send((server['host'], server['port']), 'status')
        except (asyncio.exceptions.TimeoutError, TimeoutError) as e:
            embed.description = "Server not responding"
            return embed
        except ConnectionRefusedError:
            embed.description = "Unable to connect"
            return embed
        if server['type'] == 'goon':
            embed.colour = discord.Colour.from_rgb(222, 190, 49)
        else:
            embed.colour = discord.Colour.from_rgb(150, 150, 220)
        status = worldtopic.params_to_dict(response)
        if 'station_name' in status:
            embed.title += f" ({status['station_name']})"
        if 'players' in status:
            embed.add_field(inline=True, name="players", value=status['players'])
        if 'map_name' in status:
            embed.add_field(inline=True, name="map", value=status['map_name'])
        if 'mode' in status and status['mode'] != 'secret':
            embed.add_field(inline=True, name="mode", value=status['mode'])
        elapsed = self.status_format_elapsed(status, skip_elapsed=True)
        if elapsed is not None:
            embed.add_field(inline=True, name="elapsed", value=elapsed)
        if 'shuttle_time' in status and status['shuttle_time'] != 'welp':
            shuttle_time = int(float(status['shuttle_time']))
            if shuttle_time != 360:
                eta = 'ETA' if shuttle_time >= 0 else 'ETD'
                shuttle_time = abs(shuttle_time)
                embed.add_field(inline=True, name=f"shuttle {eta}", value=self.seconds_to_hhmmss(shuttle_time))
        return embed

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def check(self, ctx: commands.Context, name: str = 'all'):
        """
        Checks the status of a Goonstation server of servers.
        `name` can be either numeric server id, the server's name, a server category like "all" or even server address.
        """
        worldtopic = self.bot.get_cog('WorldTopic')
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        futures = [asyncio.Task(self.get_status_text(s, worldtopic)) for s in servers]
        done, pending = [], futures
        message = None
        async with ctx.typing():
            while pending:
                when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
                done, pending = await asyncio.wait(pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when)
                message_text = '\n'.join(f.result() for f in futures if f.done())
                if not done:
                    continue
                if message is None:
                    message = await ctx.send(message_text)
                else:
                    await message.edit(content=message_text)

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def checkfancy(self, ctx: commands.Context, name: str = 'all'):
        """Checks the status of a Goonstation server of servers.
            `name` can be either numeric server id, the server's name or a server category like "all".
        """
        worldtopic = self.bot.get_cog('WorldTopic')
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        if len(servers) == 1:
            return await ctx.send(embed=await self.get_status_embed(servers[0], worldtopic))
        futures = [asyncio.Task(self.get_status_text(s, worldtopic, embed_url=True)) for s in servers]
        done, pending = [], futures
        message = None
        embed = discord.Embed()
        all_goon = all(server['type'] == 'goon' for server in servers)
        if all_goon:
            embed.colour = discord.Colour.from_rgb(222, 190, 49)
        else:
            embed.colour = discord.Colour.from_rgb(190, 190, 222)
        while pending:
            when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
            done, pending = await asyncio.wait(pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when)
            message_text = '\n'.join(f.result() for f in futures if f.done())
            embed.description = message_text
            if not done:
                continue
            if message is None:
                message = await ctx.send(embed=embed)
            else:
                await message.edit(embed=embed)
