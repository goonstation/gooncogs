from redbot.core.bot import Red
from .timeoutself import TimeoutSelf

async def setup(bot: Red):
    cog = TimeoutSelf(bot)
    await bot.add_cog(cog)
