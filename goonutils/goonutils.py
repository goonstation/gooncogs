from redbot.core import commands
from redbot.core.bot import Red


class GoonUtils(commands.Cog):
    """Shared utilities for Goonstation cogs."""

    def __init__(self, bot: Red):
        self.bot = bot
