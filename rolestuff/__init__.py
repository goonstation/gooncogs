from redbot.core.bot import Red
from .rolestuff import RoleStuff


def setup(bot: Red):
    bot.add_cog(RoleStuff(bot))
