import datetime
import re
import time
import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from copy import deepcopy
from redbot.core.utils.chat_formatting import box, pagify, quote
import re

class MessageCounter(commands.Cog):
    default_guild_config = {
            "words": {}
        }
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=889521548234)
        self.config.register_guild(**self.default_guild_config)

    @checks.admin()
    @commands.group()
    async def messagestats(self, ctx: commands.Context):
        """Commands for tracking how many messages matched patterns."""

    def init_word(self):
        return {
                "counter_reset_timestamp": int(time.time()),
                "counter": 0,
                "notify_targets": [],
            }

    @messagestats.command()
    async def addcounter(self, ctx: commands.Context, *, word: str):
        """Adds a counter for how many times a message with this word has been sent in this server."""
        async with self.config.guild(ctx.guild).words() as words:
            if word in words:
                await ctx.send("That word already has a counter attached")
                return
            words[word] = self.init_word()
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @messagestats.command()
    async def delcounter(self, ctx: commands.Context, *, word: str):
        """Deletes the counter for this word."""
        async with self.config.guild(ctx.guild).words() as words:
            if word not in words:
                await ctx.send("That word is not tracked")
                return
            if len(words[word]['notify_targets']):
                await ctx.send("You can't delete a word which has people or channels listening to it")
                return
            del words[word]
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @messagestats.command()
    async def checkcounter(self, ctx: commands.Context, *, word: str):
        """Checks how many messages containing this word have been sent since we started counting."""
        words = await self.config.guild(ctx.guild).words()
        if word not in words:
            await ctx.send("That word isn't tracked, use addcounter to track")
            return
        count = words[word]['counter']
        timestamp = f"<t:{words[word]['counter_reset_timestamp']}:F>"
        await ctx.send(f"`{word}` occured {count} times since {timestamp}")

    @messagestats.command()
    async def resetcounter(self, ctx: commands.Context, *, word: str):
        """Resets the counter of the word to 0 and the started-counting date to now."""
        async with self.config.guild(ctx.guild).words() as words:
            if word not in words:
                await ctx.send("That word isn't tracked, use addcounter to track")
                return
            words[word]['counter'] = 0
            words[word]['counter_reset_timestamp'] = int(time.time())
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    def resolve_target(self, target_id):
        target_id = int(target_id)
        return self.bot.get_user(target_id) or self.bot.get_channel(target_id)

    def target_mention(self, target_id):
        target = self.resolve_target(target_id)
        if target:
            return target.mention
        return None

    @messagestats.command()
    async def list(self, ctx: commands.Context):
        """Lists all words we are looking for in this server with their stored info."""
        words = await self.config.guild(ctx.guild).words()
        lines = []
        for word, data in words.items():
            timestamp = f"<t:{data['counter_reset_timestamp']}:F>"
            lines.append(f"`{word}` count {data['counter']} since {timestamp}")
            if len(data['notify_targets']):
                lines.append("\tNotifying " + " ".join(
                    self.target_mention(t) or f"`{t}`" for t in data['notify_targets']))
        if len(lines) == 0:
            await ctx.send("Nothing registered")
            return
        for page in pagify('\n'.join(lines)):
            await ctx.send(page, allowed_mentions=discord.AllowedMentions.none())

    @messagestats.command()
    async def info(self, ctx: commands.Context, *, word: str):
        """Checks the complete info of a tracked word."""
        words = await self.config.guild(ctx.guild).words()
        if not word in words:
            await ctx.send("That word is not tracked")
            return
        lines = []
        data = words[word]
        timestamp = f"<t:{data['counter_reset_timestamp']}:F>"
        lines.append(f"`{word}` count {data['counter']} since {timestamp}")
        if len(data['notify_targets']):
            lines.append("\tNotifying " + " ".join(
                self.target_mention(t) or f"`{t}`" for t in data['notify_targets']))
        await ctx.send('\n'.join(lines), allowed_mentions=discord.AllowedMentions.none())

    @messagestats.command()
    async def notifyme(self, ctx: commands.Context, *, word: str):
        """Whenever the word appears in a message on this server you will receive a DM from this bot."""
        async with self.config.guild(ctx.guild).words() as words:
            if not word in words:
                words[word] = self.init_word()
            if not ctx.author.id in words[word]['notify_targets']:
                words[word]['notify_targets'].append(ctx.author.id)
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @messagestats.command()
    async def dontnotifyme(self, ctx: commands.Context, *, word: str):
        """Turn off the notifyme trigger."""
        async with self.config.guild(ctx.guild).words() as words:
            if not word in words:
                words[word] = self.init_word()
            if ctx.author.id in words[word]['notify_targets']:
                words[word]['notify_targets'].remove(ctx.author.id)
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @messagestats.command()
    async def notifychannel(self, ctx: commands.Context, channel: discord.TextChannel, *, word: str):
        """Whenever a message containing this word appears in this server a message is sent to the set channel."""
        async with self.config.guild(ctx.guild).words() as words:
            if not word in words:
                words[word] = self.init_word()
            if not channel.id in words[word]['notify_targets']:
                words[word]['notify_targets'].append(channel.id)
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @messagestats.command()
    async def dontnotifychannel(self, ctx: commands.Context, channel: discord.TextChannel, *, word: str):
        """Turn off the notifychannel trigger."""
        async with self.config.guild(ctx.guild).words() as words:
            if not word in words:
                words[word] = self.init_word()
            if channel.id in words[word]['notify_targets']:
                words[word]['notify_targets'].remove(channel.id)
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if (
            message.guild is None
            or await self.bot.cog_disabled_in_guild(self, message.guild)
            or not hasattr(message.author, "roles")
            or message.author.bot
        ):
            return

        msg = message.clean_content
        notify_message = f"{quote(msg)}\n{message.jump_url}\nby {message.author.mention} in {message.channel.mention}\ntriggered words: "
        messages_to_send = {}
        async with self.config.guild(message.guild).words() as words:
            for word, data in words.items():
                if re.search(word, msg, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                    data['counter'] += 1
                    for target_id in data['notify_targets']:
                        target = self.resolve_target(target_id)
                        if target:
                            if not target in messages_to_send:
                                messages_to_send[target] = []
                            messages_to_send[target].append(word)
        
        for target, trig_words in messages_to_send.items():
            try:
                await target.send(notify_message + ' '.join(f"`{t}`" for t in trig_words), allowed_mentions=discord.AllowedMentions.none())
            except:
                pass
