from redbot.core.bot import Red
from .pendingappeals import PendingAppeals

async def setup(bot: Red):
    cog = PendingAppeals(bot)
    bot.add_cog(cog)
