from redbot.core.bot import Red
from .rolestuff import RoleStuff, lets_talk, GUILD_SNOWFLAKE
import logging

async def setup(bot: Red):
    cog = RoleStuff(bot)
    bot.tree.add_command(lets_talk, guild=GUILD_SNOWFLAKE)
    await bot.add_cog(cog)

async def teardown(bot: Red):
    bot.tree.remove_command(lets_talk.name, type=lets_talk.type, guild=GUILD_SNOWFLAKE)
