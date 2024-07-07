from redbot.core.bot import Red
from .goonmisc import GoonMisc


async def setup(bot: Red):
    await bot.add_cog(GoonMisc(bot))
