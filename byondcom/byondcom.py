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
        asyncio.create_task(self.session.cancel())

    @checks.admin()
    @commands.command()
    async def byondsnoop(self, ctx: commands.Context, ckey: str):
        url = f"{BASE_URL}/members/{ckey}?tab=medals&all=1"
        async with self.session.get(url) as res:
            bs = BeautifulSoup(await res.text(), "html")
            joined = None
            try:
                bs.find(id="joined").find(class_="info_text").text
            except:
                pass
            earned_fish = None
            try:
                earned_fish = b.find(src=fish_medal).parent.find(class_="smaller").text
            except:
                pass
            if joined is None:
                await ctx.send(f"Account `{ckey}` does not exist")
            else:
                out = "Account `{ckey}`:\nJoined: {joined}\n"
                if earned_fish:
                    out += "Fish " + earned_fish
                else:
                    out += "No Fish medal"
                await ctx.send(out)
        
