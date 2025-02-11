import asyncio
import aiohttp
from redbot.core import commands, app_commands, checks, Config
from redbot.core.bot import Red
from .request import GoonhubRequest
from .utilities import servers_autocomplete, success_response
import logging

class Goonhub(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.config = Config.get_conf(self, 1482189223515)
        self.config.register_global(repo=None)

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    async def build_url(self, path):
        tokens = await self.bot.get_shared_api_tokens('goonhub')
        return f"{tokens['url']}/{path}"
    
    async def check_incoming_key(self, key):
        tokens = await self.bot.get_shared_api_tokens('goonhub')
        return key == tokens['incoming_api_key']
    
    @commands.hybrid_group(name="goonhub", aliases=["hub"])
    @checks.admin()
    async def ghgroup(self, ctx: commands.Context):
        """Goonhub."""
        pass
    
    @ghgroup.command(name="setrepo")
    @app_commands.describe(repo = "The repo path without URL. E.g. goonstation/goonstation")
    async def setrepo(self, ctx: commands.Context, repo: str):
        """Set GitHub repo for commit link purposes."""
        await self.config.repo.set(repo)
        await ctx.reply(f"Repo set to `{repo}`.")
        
    @ghgroup.command(name="restart")
    @app_commands.describe(server = "The server to restart")
    @app_commands.autocomplete(server=servers_autocomplete)
    async def restart(self, ctx: commands.Context, server: str):
        """Restart a game server."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        req = await GoonhubRequest(self.bot, self.session)
        
        goonservers = self.bot.get_cog("GoonServers")
        server = goonservers.resolve_server(server)
        if not server: return await ctx.reply("Unknown server.")
                
        try:
            await req.post('orchestration/restart', data = {'server': server.tgs})
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        await success_response(ctx)
