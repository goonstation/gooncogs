import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import Optional
import datetime
import dateparser


class TimeStamp(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command()
    async def timestamp(self, ctx: commands.Context, *, time: Optional[str]):
        suffixes = "RTtDFf"
        time_obj = datetime.datetime.now() if time is None else dateparser.parse(time)
        if time_obj is None:
            await ctx.send("Sorry, I don't understand that time format")
            return
        unix_timestamp = int(time_obj.timestamp())
        stamp_lines = [f"<t:{unix_timestamp}:{s}>" for s in suffixes]
        response = "\n".join(f"{stamp} `{stamp}`" for stamp in stamp_lines)
        await ctx.send(response)
