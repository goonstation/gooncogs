from redbot.core.bot import Red
from .stopnitroscams import StopNitroScams


async def setup(bot: Red):
    await bot.add_cog(StopNitroScams(bot))
