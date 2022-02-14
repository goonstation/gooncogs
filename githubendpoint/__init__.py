from redbot.core.bot import Red
from .githubendpoint import GithubEndpoint


async def setup(bot: Red):
    bot.add_cog(GithubEndpoint(bot))
