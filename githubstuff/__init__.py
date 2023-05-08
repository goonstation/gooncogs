from redbot.core.bot import Red
from .githubstuff import GithubStuff


async def setup(bot: Red):
    await bot.add_cog(GithubStuff(bot))
