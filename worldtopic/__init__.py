from redbot.core.bot import Red
from .worldtopic import WorldTopic

def setup(bot: Red):
    bot.add_cog(WorldTopic(bot))
