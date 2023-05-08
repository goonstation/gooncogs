from redbot.core.bot import Red
from .generalapi import GeneralApi


async def setup(bot: Red):
    cog = GeneralApi(bot)
    await bot.add_cog(cog)
    await cog.init()
