from redbot.core.bot import Red
from .server_crash_endpoint import ServerCrashEndpoint

async def setup(bot: Red):
    await bot.add_cog(ServerCrashEndpoint(bot))
