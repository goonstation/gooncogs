from redbot.core.bot import Red
from .mybbnotif import MybbNotif


async def setup(bot: Red):
    cog = MybbNotif(bot)
    await bot.add_cog(cog)
    await cog.run()
