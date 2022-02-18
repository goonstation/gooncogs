from redbot.core.bot import Red
from .githubstuff import GithubStuff


def setup(bot: Red):
    bot.add_cog(GithubStuff(bot))
