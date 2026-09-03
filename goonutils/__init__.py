from redbot.core.bot import Red

from .goonutils import GoonUtils
from .text import ckeyify
from .typing import defer_or_typing, safe_typing

__all__ = ("ckeyify", "defer_or_typing", "safe_typing")


async def setup(bot: Red):
    await bot.add_cog(GoonUtils(bot))
