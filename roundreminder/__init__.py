from redbot.core.bot import Red
from .roundreminder import RoundReminder


def setup(bot: Red):
    bot.add_cog(RoundReminder(bot))
