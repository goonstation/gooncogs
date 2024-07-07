from redbot.core.bot import Red
from .timestamp import TimeStamp


async def setup(bot: Red):
    await bot.add_cog(TimeStamp(bot))
