import asyncio
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from copy import copy
import re
from typing import Optional

class RoundReminder(commands.Cog):
    default_user_settings = {'match_strings': []}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=77984122151871643842)
        self.config.register_user(**self.default_user_settings)

    def normalize(self, text):
        return ''.join(c for c in text.lower() if c.isalnum())

    @commands.command()
    async def nextround(self, ctx: commands.Context, *, search_text: Optional[str]):
        """Notifies you about the next round or the next round with server or map name containing `search_text`."""
        async with self.config.user(ctx.author).match_strings() as match_strings:
            match_strings.append(self.normalize(search_text))
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    async def notify(self, user: discord.User, message: discord.Message, match_string: str):
        await user.send(embed=message.embeds[0])

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        try:
            if message.channel.id != 421047584623427584: # TODO unhardcode #game-updates
                return
            
            embed = message.embeds[0]
            fulltext = ' '.join([embed.title] + [embed.description] + [f.name + " " + f.value for f in embed.fields])
            fulltext = self.normalize(fulltext)

            for user_id, data in (await self.config.all_users()).items():
                match_strings = data['match_strings']
                for match_string in match_strings:
                    if match_string is None or match_string in fulltext:
                        user = self.bot.get_user(user_id)
                        await self.notify(user, message, match_string)
                        if len(match_strings) == 1:
                            await self.config.user(user).match_strings.clear()
                        else:
                            match_strings.remove(match_string)
                            await self.config.user(user).match_strings.set(match_strings)
                        break
        except:
            import traceback
            return await self.bot.send_to_owners(traceback.format_exc())

