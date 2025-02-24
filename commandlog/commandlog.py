import discord
from redbot.core import commands
from redbot.core.bot import Red

class CommandLog(commands.Cog):
    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx):
        server = ctx.guild.name if ctx.guild else "direct message"
        user = ctx.author
        command = ctx.command
        channel = self.bot.get_channel(412381738510319626)
        await channel.send('{} used {} in {}'.format(user, command, server))