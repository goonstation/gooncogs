from redbot.core.bot import Red
from .editableposts import EditablePosts


def setup(bot: Red):
    bot.add_cog(EditablePosts(bot))
