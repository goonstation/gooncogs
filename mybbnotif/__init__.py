from redbot.core.bot import Red
from .mybbnotif import MybbNotif


async def setup(bot: Red):
    cog = MybbNotif(bot)
    bot.add_cog(cog)
    await cog.run()
