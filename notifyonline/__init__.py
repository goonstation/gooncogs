from redbot.core.bot import Red
from .notifyonline import NotifyOnline

async def setup(bot: Red):
    await bot.add_cog(NotifyOnline(bot))
