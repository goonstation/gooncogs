from redbot.core.bot import Red
from .norolenoinvite import NoRoleNoInvite


async def setup(bot: Red):
    await bot.add_cog(NoRoleNoInvite(bot))
