from redbot.core.bot import Red
from .byondcom import ByondCom


async def setup(bot: Red):
    cog = ByondCom(bot)
    bot.add_cog(cog)
