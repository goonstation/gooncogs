from redbot.core.bot import Red
from .betterreports import BetterReports
from discord_slash import SlashCommand


def setup(bot: Red):
    if not hasattr(bot, "slash"):
        SlashCommand(
            bot, sync_commands=True, override_type=True, sync_on_cog_reload=True
        )
    bot.add_cog(BetterReports(bot))
