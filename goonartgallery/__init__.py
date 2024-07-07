from redbot.core.bot import Red
from .goonartgallery import GoonArtGallery


async def setup(bot: Red):
    cog = GoonArtGallery(bot)
    await bot.add_cog(cog)
    await cog.init()
