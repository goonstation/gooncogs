from redbot.core.bot import Red
from .loudvideos import LoudVideos


def setup(bot: Red):
    bot.add_cog(LoudVideos(bot))
