from redbot.core.bot import Red
from .dmref import DMRef

async def setup(bot: Red):
    cog = DMRef(bot)
    bot.add_cog(cog)
    await cog.init()
