from redbot.core.bot import Red
from .stopnitroscams import StopNitroScams


def setup(bot: Red):
    bot.add_cog(StopNitroScams(bot))
