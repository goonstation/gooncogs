import asyncio
import aiohttp
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import base64
import datetime
import re

class LoginError(Exception):
    pass

class TGS(commands.Cog):
    API_VERSION = "Tgstation.Server.Api/9.2.0"
    CACHE_SERVER_LIST = True

    def __init__(self, bot: Red):
        self.bot = bot
        self.bearer = None
        self.bearer_expires = None
        self.host = None
        self.session = aiohttp.ClientSession()
        self.server_list_cache = None

    async def login(self):
        tokens = await self.bot.get_shared_api_tokens('tgs')
        self.host = tokens.get('host')
        userpass = f"{tokens.get('user')}:{tokens.get('password')}"
        async with self.session.post(
                self.host,
                headers = {
                    'Api': self.API_VERSION,
                    'Authorization': "Basic " + base64.b64encode(userpass.encode()).decode()
                    }
                ) as res:
            if res.status != 200:
                return False
            data = await res.json(content_type=None)
            # fromisoformat accepts only exactly 0, 3 or 6 decimal places; screw that
            isotime = re.sub(r'\.[0-9]*($|\+)', '\\1', data['expiresAt'])
            expires_at = datetime.datetime.fromisoformat(isotime)
            self.bearer = data['bearer']
            self.bearer_expires = expires_at
            self.session.headers.update({
                    'Api': self.API_VERSION,
                    'Authorization': "Bearer " + self.bearer,
                })
            return True

    async def get_bearer(self):
        if self.bearer_expires is not None and \
                self.bearer_expires > datetime.datetime.now(self.bearer_expires.tzinfo):
            return self.bearer
        if await self.login():
            return self.bearer
        return None

    async def assure_logged_in(self):
        if not await self.get_bearer():
            raise LoginError()

    async def list_servers(self, force_refresh=True):
        if not force_refresh and self.CACHE_SERVER_LIST and self.server_list_cache:
            return self.server_list_cache
        await self.assure_logged_in()
        # TODO support for multiple pages lol
        async with self.session.get(self.host + "/Instance/List?pageSize=100") as res:
            self.server_list_cache = (await res.json(content_type=None))['content']
            return self.server_list_cache

    async def resolve_server(self, server: Union[int, dict, str]) -> Optional[int]:
        # server id directly
        if isinstance(server, int):
            return server
        # user-friendly server name
        if isinstance(server, str):
            servers_cog = self.bot.get_cog("GoonServers")
            if servers_cog:
                server = servers_cog.resolve_server(server) or server
        # server data dict (from the GoonServers cog)
        if isinstance(server, dict):
            server = server.get('tgs')
        # tgs server id
        await self.assure_logged_in()
        if isinstance(server, str):
            for maybe_server in await self.list_servers(force_refresh=False):
                if maybe_server['name'] == server.lower():
                    server = maybe_server['id']
                    break
        # failure
        if not isinstance(server, int):
            return None
        return server

    async def restart_server(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.patch(self.host + "/DreamDaemon", headers={'Instance': str(server)}) as res:
            return await res.json(content_type=None)

    @commands.group()
    async def tgs(self, ctx: commands.Context):
        """Commands for managing TGS SS13 server instances."""

    @tgs.command()
    @checks.admin()
    async def list(self, ctx: commands.Context):
        """Lists servers managed by the current TGS instance."""
        async with ctx.typing():
            try:
                lines = []
                for server in await self.list_servers():
                    lines.append(("\N{Large Green Circle}" if server['online'] else "\N{Large Red Circle}") + \
                        f" {server['id']} | {server['name']}")
                await ctx.send('\n'.join(lines))
            except LoginError:
                await ctx.send("Unable to login, please contact the bot owner and/or the TGS instance administrator.")

    @tgs.command()
    @checks.admin()
    async def reboot(self, ctx: commands.Context, server: str):
        """Reboots a given server.
        
        `server`: server name of the server you want to restart (NOT its tgs ID)"""
        async with ctx.typing():
            try:
                response = await self.restart_server(server)
                if response is None:
                    return await ctx.send("Could not find server.")
                if 'errorCode' in response:
                    return await ctx.send(f"{response['message']} (error code {response['errorCode']})")
                await ctx.send("Server restarting.")
            except LoginError:
                await ctx.send("Unable to login, please contact the bot owner and/or the TGS instance administrator.")
