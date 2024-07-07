from redbot.core.bot import Red
from .listthreads import ListThreads

async def setup(bot: Red):
    cog = ListThreads(bot)
    await bot.add_cog(cog)
