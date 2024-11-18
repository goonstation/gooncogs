from redbot.core.bot import Red
from .spacebeecentcom import SpacebeeCentcom, check_link, GUILD_ID
import discord


async def setup(bot: Red):
    cog = SpacebeeCentcom(bot)
    bot.tree.add_command(check_link, guild = discord.Object(GUILD_ID))
    await bot.add_cog(cog)
    await cog.init()

async def teardown(bot: Red):
    bot.tree.remove_command(check_link.name, check_link.type, guild = discord.Object(GUILD_ID))
