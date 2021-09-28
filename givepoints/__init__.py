from redbot.core.bot import Red
from .givepoints import GivePoints


def setup(bot: Red):
    bot.add_cog(GivePoints(bot))
