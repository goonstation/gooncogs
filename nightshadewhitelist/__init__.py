from redbot.core.bot import Red
from .nightshadewhitelist import NightshadeWhitelist


async def setup(bot: Red):
    await bot.add_cog(NightshadeWhitelist(bot))
