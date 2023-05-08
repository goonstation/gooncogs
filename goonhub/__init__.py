from redbot.core.bot import Red
from .goonhub import GoonHub

async def setup(bot: Red):
    cog = GoonHub(bot)
    await bot.add_cog(cog)
