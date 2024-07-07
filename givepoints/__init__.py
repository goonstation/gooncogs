from redbot.core.bot import Red
from .givepoints import GivePoints


async def setup(bot: Red):
    await bot.add_cog(GivePoints(bot))
