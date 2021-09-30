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

    @commands.command()
    @checks.admin()
    async def whois(self, ctx: commands.Context, server_id: str, *, query: str):
        goonservers = self.bot.get_cog('GoonServers')
        response = await goonservers.send_to_server_safe(server_id, {
                'type': "whois",
                'taget': query,
            }, ctx.message, to_dict=True)

        count = int(response['count'])
        out = []
        for i in range(1, count + 1):
            rolestuff = response.get(f"role{i}", "jobless")
            if response.get(f"dead{i}"):
                rolestuff += " DEAD"
            if response.get(f"t{i}"):
                rolestuff += " \N{REGIONAL INDICATOR SYMBOL LETTER T}"
            line = response.get(f"name{i}", "-") + \
                " (" + response.get(f"ckey{i}", "-") + ") [" + rolestuff + "]"
            out.append(line)
        if out:
            await ctx.send("\n".join(out))
        else:
            await ctx.send("No one found.")
