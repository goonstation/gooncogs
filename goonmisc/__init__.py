from redbot.core.bot import Red
from .goonmisc import GoonMisc


def setup(bot: Red):
    bot.add_cog(GoonMisc(bot))
