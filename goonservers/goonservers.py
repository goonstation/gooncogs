import asyncio
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import socket
import re
import datetime
import random
from collections import OrderedDict

class GoonServers(commands.Cog):
    INITIAL_CHECK_TIMEOUT = 0.2
    ALLOW_ADHOC = True
    COLOR_GOON = discord.Colour.from_rgb(222, 190, 49)
    COLOR_OTHER = discord.Colour.from_rgb(130, 130, 222)
    COLOR_ERROR = discord.Colour.from_rgb(220, 150, 150)


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
        name = name.lower()
        single_server = self.resolve_server(name)
        if single_server is not None:
            return [single_server]
        if name not in self.categories:
            return []
        return [self.resolve_server(x) for x in self.categories[name]]

    def seconds_to_hhmmss(self, input_seconds):
        hours, remainder = divmod(input_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

    def status_format_elapsed(self, status):
        elapsed = status.get('elapsed') or status.get('round_duration') or status.get('stationtime')
        if elapsed == 'pre':
            elapsed = "preround"
        elif elapsed == 'post':
            elapsed = "finished"
        elif elapsed is not None:
            try:
                elapsed = self.seconds_to_hhmmss(int(elapsed))
            except ValueError:
                pass
        return elapsed

    async def get_status_info(self, server, worldtopic):
        result = OrderedDict()
        result['full_name'] = server.get('full_name') or server['host']
        result['url'] = server.get('url')
        result['type'] = server['type']
        result['error'] = None
        try:
            response = await worldtopic.send((server['host'], server['port']), 'status')
        except (asyncio.exceptions.TimeoutError, TimeoutError) as e:
            result['error'] = "Server not responding."
            return result
        except (socket.gaierror, ConnectionRefusedError) as e:
            result['error'] = "Unable to connect."
            return result
        if response is None:
            result['error'] = "Invalid server response."
            return result
        status = worldtopic.params_to_dict(response)
        result['station_name'] = status.get('station_name')
        result['players'] = int(status['players']) if 'players' in status else None
        result['map'] = status.get('map_name')
        result['mode'] = status.get('mode')
        result['time'] = self.status_format_elapsed(status)
        result['shuttle'] = None
        result['shuttle_eta'] = None
        if 'shuttle_time' in status and status['shuttle_time'] != 'welp':
            shuttle_time = int(status['shuttle_time'])
            if shuttle_time != 360:
                eta = 'ETA' if shuttle_time >= 0 else 'ETD'
                shuttle_time = abs(shuttle_time)
                result['shuttle'] = self.seconds_to_hhmmss(shuttle_time)
                result['shuttle_eta'] = eta
        return result

    def status_result_parts(self, status_info):
        result_parts = []
        if status_info['station_name']:
            result_parts.append(status_info['station_name'])
        if status_info['players'] is not None:
            result_parts.append(f"{status_info['players']} player" + ('s' if status_info['players'] != 1 else ''))
        if status_info['map']:
            result_parts.append(f"map: {status_info['map']}")
        if status_info['mode'] and status_info['mode'] != "secret":
            result_parts.append(f"mode: {status_info['mode']}")
        if status_info['time']:
            result_parts.append(f"time: {status_info['time']}")
        if status_info['shuttle_eta']:
            result_parts.append(f"shuttle {status_info['shuttle_eta']}: {status_info['shuttle']}")
        return result_parts

    def generate_status_text(self, status_info, embed_url=False):
        result = status_info['full_name']
        if embed_url and status_info['url']:
            result = f"[{result}]({status_info['url']})"
        result = f"**{result}** "
        if status_info['error']:
            return result + status_info['error']
        result += " | ".join(self.status_result_parts(status_info))
        if not embed_url and status_info['url']:
            result += " " + status_info['url']
        return result

    def generate_status_embed(self, status_info, embed=None):
        if embed is None:
            embed = discord.Embed()
        embed.title = status_info['full_name']
        if status_info['url']:
            embed.url = status_info['url']
        if status_info['error']:
            embed.description = status_info['error']
            embed.colour = self.COLOR_ERROR 
            return embed
        if status_info['type'] == 'goon':
            embed.colour = self.COLOR_GOON
        else:
            embed.colour = self.COLOR_OTHER
        embed.description = " | ".join(self.status_result_parts(status_info))
        return embed

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def checkclassic(self, ctx: commands.Context, name: str = 'all'):
        """
        Checks the status of a Goonstation server of servers.
        `name` can be either numeric server id, the server's name, a server category like "all" or even server address.
        """

        if name.lower() in self.CHECK_GIMMICKS:
            result = await self.CHECK_GIMMICKS[name.lower()](self, ctx)
            if result:
                await ctx.send(result)
                return

        worldtopic = self.bot.get_cog('WorldTopic')
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        futures = [asyncio.Task(self.get_status_info(s, worldtopic)) for s in servers]
        done, pending = [], futures
        message = None
        async with ctx.typing():
            while pending:
                when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
                done, pending = await asyncio.wait(pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when)
                message_text = '\n'.join(self.generate_status_text(f.result()) for f in futures if f.done())
                if not done:
                    continue
                if message is None:
                    message = await ctx.send(message_text)
                else:
                    await message.edit(content=message_text)

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(10, wait=False)
    async def check(self, ctx: commands.Context, name: str = 'all'):
        """Checks the status of a Goonstation server of servers.
            `name` can be either numeric server id, the server's name or a server category like "all".
        """
        if not ctx.channel.guild.me.guild_permissions.embed_links:
            return await self.checkclassic(ctx, name)

        embed = discord.Embed()
        embed.colour = self.COLOR_GOON

        if name.lower() in self.CHECK_GIMMICKS:
            result = await self.CHECK_GIMMICKS[name.lower()](self, ctx)
            if result:
                embed.description = result
                await ctx.send(embed=embed)
                return

        worldtopic = self.bot.get_cog('WorldTopic')
        servers = self.resolve_server_or_category(name)
        if not servers:
            return await ctx.send("Unknown server.")
        single_server_embed = len(servers) == 1
        futures = [asyncio.Task(self.get_status_info(s, worldtopic)) for s in servers]
        done, pending = [], futures
        message = None
        all_goon = all(server['type'] == 'goon' for server in servers)
        if not all_goon:
            embed.colour = self.COLOR_OTHER
        async with ctx.typing():
            while pending:
                when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
                done, pending = await asyncio.wait(pending, timeout=self.INITIAL_CHECK_TIMEOUT, return_when=when)
                if not single_server_embed:
                    message_text = '\n'.join(self.generate_status_text(f.result(), embed_url=True) for f in futures if f.done())
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

    CHECK_GIMMICKS = {
            'oven': _check_gimmick_oven,
            'goonstation': _check_gimmick_goonstation,
        }
