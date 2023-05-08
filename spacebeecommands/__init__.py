from redbot.core.bot import Red
from .spacebeecommands import SpacebeeCommands


async def setup(bot: Red):
    await bot.add_cog(SpacebeeCommands(bot))
