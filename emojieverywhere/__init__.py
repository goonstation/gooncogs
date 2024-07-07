from redbot.core.bot import Red
from .emojieverywhere import EmojiEverywhere


async def setup(bot: Red):
    await bot.add_cog(EmojiEverywhere(bot))
