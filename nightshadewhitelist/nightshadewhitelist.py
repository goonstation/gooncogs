import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
from fastapi import Request
from fastapi.responses import PlainTextResponse
import re
import time
import functools


class NightshadeWhitelist(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.cached_whitelist_txt = None
        self.config = Config.get_conf(self, identifier=32578896542315)
        self.config.register_global(fixed_ckeys=[])
        self.config.register_user(ckey=None)

    async def get_whitelist_txt(self):
        if self.cached_whitelist_txt is not None:
            return self.cached_whitelist_txt
        lines = []
        for user_id, data in (await self.config.all_users()).items():
            if data.get("ckey"):
                lines.append(data["ckey"])
        for ckey in await self.config.fixed_ckeys():
            lines.append(ckey)
        self.cached_whitelist_txt = "\n".join(lines) + "\n"
        return self.cached_whitelist_txt

    def invalidate_whitelist_cache(self):
        self.cached_whitelist_txt = None

    def register_to_general_api(self, app):
        @app.get("/nightshade_whitelist", response_class=PlainTextResponse)
        async def nightshade_whitelist():
            return await self.get_whitelist_txt()

    async def send_to_nightshade(self, data):
        goonservers = self.bot.get_cog("GoonServers")
        subtype = goonservers.subtypes["nightshade"]
        return await goonservers.send_to_servers(subtype.servers, data)

    @commands.command()
    async def ss13link(self, ctx: commands.Context, *, ckey: str):
        """Links your account to a BYOND username to whitelist you on the Nightshade SS13 servers."""
        current_ckey = await self.config.user(ctx.author).ckey()
        if current_ckey is not None:
            await ctx.send(
                f"You already have ckey '{current_ckey}' bound do your account. Use the ss13unlink command to unlink it first."
            )
            return
        ckey = "".join(c.lower() for c in ckey if c.isalnum())
        await self.config.user(ctx.author).ckey.set(ckey)
        self.invalidate_whitelist_cache()
        await ctx.send(f"You are now whitelisted as ckey '{ckey}'.")
        await self.send_to_nightshade(
            {
                "type": "whitelistChange",
                "wlType": "add",
                "ckey": ckey,
            }
        )

    @commands.command()
    async def ss13unlink(self, ctx: commands.Context):
        """Links your account from a BYOND username so you can use a different BYOND account instead."""
        current_ckey = await self.config.user(ctx.author).ckey()
        if current_ckey is None:
            await ctx.send(f"You don't have a ckey bound to your account.")
            return
        await self.config.user(ctx.author).ckey.set(None)
        self.invalidate_whitelist_cache()
        await ctx.send(
            f"Ckey '{current_ckey}' unbound from your account. You are no longer whitelisted."
        )
        await self.send_to_nightshade(
            {
                "type": "whitelistChange",
                "wlType": "remove",
                "ckey": current_ckey,
            }
        )
