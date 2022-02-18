from redbot.core.bot import Red
from .goonservers import GoonServers


async def setup(bot: Red):
    cog = GoonServers(bot)
    bot.add_cog(cog)
    await cog.reload_config()
