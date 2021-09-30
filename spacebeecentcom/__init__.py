from redbot.core.bot import Red
from .spacebeecentcom import SpacebeeCentcom

async def setup(bot: Red):
    bot.add_cog(SpacebeeCentcom(bot))
