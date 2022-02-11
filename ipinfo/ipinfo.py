import asyncio
import aiohttp
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *

class IPInfo(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.cancel())

    @checks.admin()
    @commands.command()
    async def ipinfo(self, ctx: commands.Context, ip: str):
        tokens = await self.bot.get_shared_api_tokens('vpnapi')
        url = f"https://vpnapi.io/api/[ip]?key={tokens['api_key']}"
        out = ""
        async with self.session.get(url) as res:
            if res.status != 200:
                await ctx.send(f"Error code {res.status} occured when querying the API")
                return
            data = await res.json()
            security_stuff = [k for k, v in data['security'].items() if v] or ["not-VPN"]
            maps_link = f"https://www.google.com/maps/place/{data['location']['latitude']},{data['location']['longtitude']}"
            message = """`{data['ip']}`
{' '.join(security_stuff)}
{maps_link}
{location['country']}, {location['region']}, {location['city']}
"""
            await ctx.send(message)
