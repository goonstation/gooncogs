from redbot.core.bot import Red
from .messagecounter import MessageCounter

async def setup(bot: Red):
    await bot.add_cog(MessageCounter(bot))
