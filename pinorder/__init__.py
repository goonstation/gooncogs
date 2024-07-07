from redbot.core.bot import Red
from .pinorder import PinOrder


async def setup(bot: Red):
    await bot.add_cog(PinOrder(bot))
