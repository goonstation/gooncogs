from redbot.core.bot import Red
from .dmref import DMRef

async def setup(bot: Red):
    cog = DMRef(bot)
    await bot.add_cog(cog)
    await cog.init()
