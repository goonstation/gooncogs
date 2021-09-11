from redbot.core.bot import Red
from .norolenoinvite import NoRoleNoInvite


def setup(bot: Red):
    bot.add_cog(NoRoleNoInvite(bot))
