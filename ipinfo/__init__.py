from redbot.core.bot import Red
from .ipinfo import IPInfo


async def setup(bot: Red):
    cog = IPInfo(bot)
    await bot.add_cog(cog)
