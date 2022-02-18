from redbot.core.bot import Red
from .rolestuff import RoleStuff


async def setup(bot: Red):
    cog = RoleStuff(bot)
    bot.add_cog(cog)
