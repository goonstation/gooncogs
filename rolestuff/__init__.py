from redbot.core.bot import Red
from .rolestuff import RoleStuff


async def setup(bot: Red):
    cog = RoleStuff(bot)
    await bot.add_cog(cog)
