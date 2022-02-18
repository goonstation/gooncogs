from redbot.core.bot import Red
from .timestamp import TimeStamp


def setup(bot: Red):
    bot.add_cog(TimeStamp(bot))
