from redbot.core.bot import Red
from .spacebeecentcom import SpacebeeCentcom


async def setup(bot: Red):
    cog = SpacebeeCentcom(bot)
    bot.add_cog(cog)
    await cog.init()
