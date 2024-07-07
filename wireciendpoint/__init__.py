from redbot.core.bot import Red
from .wireciendpoint import WireCiEndpoint


async def setup(bot: Red):
    await bot.add_cog(WireCiEndpoint(bot))
