from redbot.core.bot import Red
from .pinorder import PinOrder

def setup(bot: Red):
    bot.add_cog(PinOrder(bot))
