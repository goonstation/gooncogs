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
from pprint import pformat
from redbot.core.utils.chat_formatting import box, pagify

class LoginError(Exception):
    pass

class UnknownServerError(Exception):
    pass

class HttpStatusCodeError(Exception):
    def __init__(self, status, data):
        self.status = status
        self.data = data

    def __str__(self):
        return f"HTTP Status code {self.status}"

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

    def _parse_iso_time(self, text):
        # fromisoformat accepts only exactly 0, 3 or 6 decimal places; screw that
        text = re.sub(r'\.[0-9]*($|\+)', '\\1', text)
        return datetime.datetime.fromisoformat(text)

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
            expires_at = self._parse_iso_time(data['expiresAt'])
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
            data = await res.json(content_type=None)
            if 'content' not in data:
                return await self.process_response(res)
            self.server_list_cache = data['content']
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
            raise UnknownServerError()
        return server

    async def process_response(self, response):
        result = await response.json(content_type=None)
        if not result and str(response.status)[0] != '2':
            raise HttpStatusCodeError(response.status, response)
        if response.status == 204: # 204: No Content
            return {}
        return result

    async def server_restart(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.patch(self.host + "/DreamDaemon", headers={'Instance': str(server)}) as res:
            return await self.process_response(res)

    async def server_diag(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.patch(self.host + "/DreamDaemon/Diagnostics", headers={'Instance': str(server)}) as res:
            return await self.process_response(res)

    async def server_info(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.get(self.host + "/DreamDaemon", headers={'Instance': str(server)}) as res:
            return await self.process_response(res)

    async def server_start(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.put(self.host + "/DreamDaemon", headers={'Instance': str(server)}) as res:
            return await self.process_response(res)

    async def server_stop(self, server):
        server = await self.resolve_server(server)
        if server is None:
            return None
        await self.assure_logged_in()
        async with self.session.delete(self.host + "/DreamDaemon", headers={'Instance': str(server)}) as res:
            return await self.process_response(res)

    @checks.admin()
    @commands.group()
    async def tgs(self, ctx: commands.Context):
        """Commands for managing TGS SS13 server instances."""

    async def run_request(self, ctx: commands.Context, request):
        async with ctx.typing():
            try:
                response = await request
                if response is None:
                    await ctx.send("Unknown error.")
                elif isinstance(response, dict) and 'errorCode' in response:
                    await ctx.send(f"{response['message']} (error code: {response['errorCode']})")
                else:
                    return response
            except HttpStatusCodeError as e:
                if e.status == 403:
                    await ctx.send(f"Insuffiecient TGS user permissions (HTTP error code: {e.status})")
                elif e.status == 503:
                    await ctx.send(f"TGS server is starting up or shutting down. (HTTP error code: {e.status})")
                elif e.status == 401:
                    await ctx.send(f"Invalid TGS authentication, please contact bot owner. (HTTP error code: {e.status})")
                else:
                    await ctx.send(f"HTTP status code: {e.status}")
            except UnknownServerError:
                await ctx.send("Unknown server name.")
            except LoginError:
                await ctx.send("Unable to login, please contact the bot owner and/or the TGS instance administrator.")
            except aiohttp.ClientConnectorError:
                await ctx.send("Unable to connect to the server, please contact the bot owner and/or the TGS instance administrator.")
        return None

    @tgs.command()
    @checks.admin()
    async def list(self, ctx: commands.Context):
        """Lists servers managed by the current TGS instance."""
        response = await self.run_request(ctx, self.list_servers())
        if response is None:
            return
        lines = []
        for server in response:
            lines.append(("\N{Large Green Circle}" if server['online'] else "\N{Large Red Circle}") + \
                f" {server['id']} | {server['name']}")
        await ctx.send('\n'.join(lines))

    @tgs.command(aliases=["restart"])
    @checks.admin()
    async def reboot(self, ctx: commands.Context, server: str):
        """Reboots a given server.
        
        `server`: server name of the server you want to restart (NOT its tgs ID)"""
        response = await self.run_request(ctx, self.server_restart(server))
        if response is not None:
            await ctx.send("Server restarting")

    @tgs.command()
    @checks.admin()
    async def start(self, ctx: commands.Context, server: str):
        """Starts a given server.
        
        `server`: server name of the server you want to start (NOT its tgs ID)"""
        response = await self.run_request(ctx, self.server_start(server))
        if response is not None:
            await ctx.send("Server starting")

    @tgs.command()
    @checks.admin()
    async def stop(self, ctx: commands.Context, server: str):
        """Stops a given server.
        
        `server`: server name of the server you want to stop (NOT its tgs ID)"""
        response = await self.run_request(ctx, self.server_stop(server))
        if response is not None:
            await ctx.send("Server stopping")

    @tgs.command()
    @checks.admin()
    async def rawdiag(self, ctx: commands.Context, server: str):
        """Gets raw diagnostics of a given server.
        
        `server`: server name of the server you want to get diagnostics of (NOT its tgs ID)"""
        response = await self.run_request(ctx, self.server_diag(server))
        if response is not None:
            for page in pagify(pformat(response)):
                await ctx.send(box(page, lang='json'))

    @tgs.command()
    @checks.admin()
    async def rawinfo(self, ctx: commands.Context, server: str):
        """Gets raw info about a given server.
        
        `server`: server name of the server you want to get info of (NOT its tgs ID)"""
        response = await self.run_request(ctx, self.server_info(server))
        if response is not None:
            for page in pagify(pformat(response)):
                await ctx.send(box(page, lang='json'))

    @tgs.command()
    @checks.admin()
    async def info(self, ctx: commands.Context, server: str):
        """Gets info about a given server.
        
        `server`: server name of the server you want to get info of (NOT its tgs ID)"""
        res = await self.run_request(ctx, self.server_info(server))
        if res is None:
            return
        server_name = server
        servers_cog = self.bot.get_cog("GoonServers")
        server_info = {}
        if servers_cog:
            server_info = servers_cog.resolve_server(server) or {}
            server_name = server_info.get('full_name', server_name)

        embed = discord.Embed()
        if 'url' in server_info:
            embed.url = server_info['url']
        embed.title = server_name
        embed.colour = [
          discord.Colour.from_rgb(200, 100, 100),
          discord.Colour.from_rgb(200, 200, 100),
          discord.Colour.from_rgb(100, 170, 100),
          discord.Colour.from_rgb(200, 150, 100)
          ][res['status']]
        embed.description = box(res['activeCompileJob']['output']) + "\n"
        desc_timestamp = None
        if 'stoppedAt' in res['activeCompileJob']['job']:
            desc_timestamp = res['activeCompileJob']['job']['stoppedAt']
            embed.description += "Compilation finished "
        else:
            desc_timestamp = res['activeCompileJob']['job']['startedAt']
            embed.description += "Compilation in progress, started "
        embed.description += f"<t:{int(self._parse_iso_time(desc_timestamp).timestamp())}:F>"
        embed.add_field(name="watchdog status", value=["Offline", "Restoring", "Online", "Delayed Restart"][res['status']])
        embed.add_field(name="byond version", value=res['activeCompileJob']['byondVersion'])
        commit_url = res['activeCompileJob']['repositoryOrigin'] + "/commit/" + res['activeCompileJob']['revisionInformation']['originCommitSha']
        commit_hash = res['activeCompileJob']['revisionInformation']['originCommitSha'][:7]
        embed.add_field(name="commit", value=f"[{commit_hash}]({commit_url})")
        embed.set_footer(text=f"port: {res.get('currentPort', res.get('port', 'unknown'))}")
        embed.timestamp = self._parse_iso_time(res['activeCompileJob']['job']['startedAt'])
        if res['activeCompileJob']['revisionInformation']['activeTestMerges']:
          embed.add_field(name="test merges", value="TODO")
        await ctx.send(embed=embed)
