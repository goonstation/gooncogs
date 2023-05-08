from redbot.core.bot import Red
from .editableposts import EditablePosts


async def setup(bot: Red):
    await bot.add_cog(EditablePosts(bot))
