from redbot.core.bot import Red
from .goonhub import Goonhub
from .builds import GoonhubBuilds
from .testmerges import GoonhubTestmerges
from .notes import GoonhubNotes
import goonhub.settings as settings

async def setup(bot: Red):
    settings.Bot = bot

    cog = Goonhub(bot)
    await bot.add_cog(cog)
    builds = GoonhubBuilds(cog)
    await bot.add_cog(builds)
    testmerges = GoonhubTestmerges(cog)
    await bot.add_cog(testmerges)
    notes = GoonhubNotes(cog)
    await bot.add_cog(notes)
