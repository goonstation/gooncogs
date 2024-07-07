"""Package for Wikiss13 cog."""
import json
from pathlib import Path

from redbot.core.bot import Red

from .wikiss13 import Wikiss13

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot: Red) -> None:
    """Load Wikss13 cog."""
    cog = Wikiss13()
    await bot.add_cog(cog)
