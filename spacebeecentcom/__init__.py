from redbot.core.bot import Red
from .spacebeecentcom import SpacebeeCentcom


async def setup(bot: Red):
    cog = SpacebeeCentcom(bot)
    await bot.add_cog(cog)
    await cog.init()
