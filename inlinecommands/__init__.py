from redbot.core.bot import Red
from .inlinecommands import InlineCommands


async def setup(bot: Red):
    await bot.add_cog(InlineCommands(bot))
