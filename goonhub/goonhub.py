import asyncio
import aiohttp
from redbot.core import commands, app_commands, checks, Config
from redbot.core.bot import Red

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
    
    @commands.hybrid_group(name="gh", aliases=["goonhub"])
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
