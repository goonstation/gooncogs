import asyncio
import aiohttp
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import logging
import datetime
from bs4 import BeautifulSoup
import itertools

BASE_URL = "http://www.byond.com"
FISH_MEDAL = "http://www.byond.com/games/hubmedal/4893.png"


class ByondCom(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    @checks.admin()
    @commands.command(aliases=["byondinfo"])
    async def byondsnoop(self, ctx: commands.Context, ckey: str):
        url = f"{BASE_URL}/members/{ckey}?tab=medals&all=1"
        async with self.session.get(url) as res:
            bs = BeautifulSoup(await res.text(), features="html.parser")
            joined = None
            try:
                joined = bs.find(id="joined").find(class_="info_text").text
            except AttributeError:
                pass
            if joined is None:
                await ctx.send(f"Account `{ckey}` does not exist")
                return
            earned_fish = None
            try:
                earned_fish = bs.find(src=FISH_MEDAL).parent.find(class_="smaller").text
            except AttributeError:
                pass
            description = None
            try:
                description = bs.find(id="description").text
            except AttributeError:
                pass
            out = f"Account `{ckey}`:\nJoined BYOND: {joined}\n"
            if earned_fish:
                out += "Fish " + earned_fish
            else:
                out += "No Fish medal"
            if description:
                out += f"\nAccount description: `{description}`"
            out += f"\nMedals page: <{url}>"
            await ctx.send(out)

    async def get_medals(self, ckey: str):
        url = f"{BASE_URL}/members/{ckey}?tab=medals&all=1"
        async with self.session.get(url) as res:
            bs = BeautifulSoup(await res.text(), "html")
            if bs.find(id="joined") is None:
                return None
            return [m.text for m in bs.find_all(class_="medal_name")]

    @commands.command()
    @commands.cooldown(3, 3)
    @commands.max_concurrency(10, wait=False)
    async def hasmedal(self, ctx: commands.Context, ckey: str, *, medal: str):
        orig_medal = medal.strip('"')
        target_medal = "".join(c for c in orig_medal if c.isalpha()).lower()
        medals = await self.get_medals(ckey)
        if medals is None:
            await ctx.send(f"Account `{ckey}` does not exist")
            return
        for medal in medals:
            if target_medal == "".join(c for c in medal if c.isalpha()).lower():
                await ctx.send(f"Account `{ckey}` has medal `{medal}`")
                return
        await ctx.send(
            f"Account `{ckey}` does not have the medal `{orig_medal.title()}`"
        )

    @checks.admin()
    @commands.command()
    async def otherserversplayed(self, ctx: commands.Context, ckey):
        await ctx.reply(f"You need to check this manually here: https://crawler.station13.ru/?ckey={ckey}")

    # disabled due to Cloudflare blocking bot access
    async def otherserversplayed_disabled(self, ctx: commands.Context, ckey):
        url = "https://crawler.station13.ru/api/?ckey=" + ckey
        output = []
        async with self.session.get(url) as res:
            data = await res.json(content_type='text/plain')
            for serverinfo in data:
                if 'bypass' in serverinfo:
                    if serverinfo['bypass'] != 0:
                        output.append(f"'Bypass' is {serverinfo['bypass']} but no idea what that means")
                elif 'servername' in serverinfo and 'count' in serverinfo:
                    output.append(f"`{serverinfo['servername']}`: {serverinfo['count']}")
        if not output:
            await ctx.send("Ckey not found")
            return
        await ctx.send("\n".join(output))
