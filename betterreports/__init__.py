from redbot.core.bot import Red
from .betterreports import BetterReports


async def setup(bot: Red):
    await bot.add_cog(BetterReports(bot))
