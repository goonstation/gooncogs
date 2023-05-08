from redbot.core.bot import Red
from .worldtopic import WorldTopic


async def setup(bot: Red):
    await bot.add_cog(WorldTopic(bot))
