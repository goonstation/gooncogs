from redbot.core.bot import Red
from .roundreminder import RoundReminder


async def setup(bot: Red):
    await bot.add_cog(RoundReminder(bot))
