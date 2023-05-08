from redbot.core.bot import Red
from .loudvideos import LoudVideos


async def setup(bot: Red):
    await bot.add_cog(LoudVideos(bot))
