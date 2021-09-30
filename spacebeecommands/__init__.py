from redbot.core.bot import Red
from .spacebeecommands import SpacebeeCommands

async def setup(bot: Red):
    bot.add_cog(SpacebeeCommands(bot))
