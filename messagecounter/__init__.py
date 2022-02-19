from redbot.core.bot import Red
from .messagecounter import MessageCounter

def setup(bot: Red):
    bot.add_cog(MessageCounter(bot))
