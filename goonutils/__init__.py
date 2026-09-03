from redbot.core.bot import Red

from .goonutils import GoonUtils
from .typing import defer_or_typing, safe_typing

__all__ = ("defer_or_typing", "safe_typing")


async def setup(bot: Red):
    await bot.add_cog(GoonUtils(bot))
