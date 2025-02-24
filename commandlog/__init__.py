from redbot.core.bot import Red
from .commandlog import CommandLog

async def setup(bot: Red):
    cog = CommandLog(bot)
    await bot.add_cog(cog)
