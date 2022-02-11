from redbot.core.bot import Red
from .ipinfo import IPInfo

async def setup(bot: Red):
    cog = IPInfo(bot)
    bot.add_cog(cog)
