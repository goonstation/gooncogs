from redbot.core.bot import Red
from .inlinecommands import InlineCommands

def setup(bot: Red):
    bot.add_cog(InlineCommands(bot))
