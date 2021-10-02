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

class SpacebeeCommands(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    def format_whois(self, response):
        count = int(response['count'])
        out = []
        for i in range(1, count + 1):
            rolestuff = response.get(f"role{i}", "jobless")
            if response.get(f"dead{i}"):
                rolestuff += " DEAD"
            if response.get(f"t{i}"):
                rolestuff += " \N{REGIONAL INDICATOR SYMBOL LETTER T}"
            line = response.get(f"name{i}", "-") + \
                " (" + response.get(f"ckey{i}", "-") + ") " + rolestuff
            out.append(line)
        if out:
            return '\n'.join(out)
        return "No one found."

    @commands.command()
    @checks.admin()
    async def whois(self, ctx: commands.Context, server_id: str, *, query: str):
        """Looks for a person on a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "whois",
                'target': query,
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(self.format_whois(response))

    @commands.command()
    async def players(self, ctx: commands.Context, server_id: str):
        """Lists players on a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, "status", ctx.message, to_dict=True)
        if response is None:
            return
        players = []
        try:
            for i in range(int(response['players'])):
                players.append(response[f'player{i}'])
        except KeyError:
            await ctx.message.reply("That server is not responding correctly.")
            return
        players.sort()
        if players:
            await ctx.message.reply(", ".join(players))
        else:
            await ctx.message.reply("No players.")

    @commands.command()
    @checks.admin()
    async def ooc(self, ctx: commands.Context, server_id: str, *, message: str):
        """Sends an OOC message to a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        await goonservers.send_to_server_safe(server_id, {
                'type': "ooc",
                'msg': message,
                'nick': f"(Discord) {ctx.author.name}",
            }, ctx.message, react_success=True)

    @commands.command()
    @checks.admin()
    async def antags(self, ctx: commands.Context, server_id: str):
        """Lists antagonists on a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "antags",
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(self.format_whois(response))

    @commands.command()
    @checks.admin()
    async def ailaws(self, ctx: commands.Context, server_id: str):
        """Lists current AI laws on a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "ailaws",
            }, ctx, to_dict=True)
        if response is None:
            return
        if response == 0.0:
            await ctx.send("Round hasn't started yet.")
            return
        out = []
        for key, value in sorted(response.items()):
            try:
                key = int(key)
            except ValueError:
                continue
            out.append(f"{key}: {value}")
        if out:
            await ctx.send('\n'.join(out))
        else:
            await ctx.send("No AI laws.")

    @commands.command(aliases=["hcheck"])
    @checks.admin()
    async def scheck(self, ctx: commands.Context, server_id: str):
        """Checks server health of a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "health",
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(f"CPU: {response['cpu']}\ntime scaling: {response['time']}")

    @commands.command()
    @checks.admin()
    async def rev(self, ctx: commands.Context, server_id: str):
        """Checks code revision of a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "rev",
            }, ctx, to_dict=True)
        if response is None:
            return
        rev, author = response['msg'].split(" by ")
        await ctx.send(response['msg'] + "\nhttps://github.com/goonstation/goonstation/commit/" + rev)

    @commands.command()
    @checks.admin()
    async def version(self, ctx: commands.Context, server_id: str):
        """Checks BYOND version of a given Goonstation server."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "version",
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(f"BYOND {response['major']}.{response['minor']}\nGoonhub: {response['goonhub_api']}")

    @commands.command()
    @checks.admin()
    async def delay(self, ctx: commands.Context, server_id: str):
        """Delays a Goonstation round end."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "delay",
                'nick': ctx.message.author.name,
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(response['msg'])

    @commands.command()
    @checks.admin()
    async def undelay(self, ctx: commands.Context, server_id: str):
        """Undelays a Goonstation round end."""
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "undelay",
                'nick': ctx.message.author.name,
            }, ctx, to_dict=True)
        if response is None:
            return
        await ctx.send(response['msg'])

    @commands.command()
    @checks.is_owner()
    async def playsound(self, ctx: commands.Context, server_id: str):
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "youtube",
                'data': '{"key":"Pali6","title":"test","duration":4,"file":"https://file-examples-com.github.io/uploads/2017/11/file_example_OOG_1MG.ogg"}',
            }, ctx, to_dict=True)
        if response is None:
            return
