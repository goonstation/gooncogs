import random
import asyncio
import re
import requests
import discord
import contextlib
import io
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from discord_slash import SlashCommand, SlashContext
from discord_slash.cog_ext import cog_slash
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from typing import Optional


class EmojiEverywhere(commands.Cog):
    EMOJI_REGEX = re.compile("<(a?):([^:]+):#?([0-9]+)>")
    GIF_HEADER = b"\x47\x49\x46\x38\x39\x61"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8884216513511451)
        self.config.init_custom("stealable_emoji", 1)
        self.config.register_custom("stealable_emoji", urls=[])
        self.config.register_global(emoji_guild=None, emoji_log_channel=None)

        self.bttv_enabled = False

    @commands.command()
    @commands.is_owner()
    async def set_emoji_log(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel]
    ):
        if channel is None:
            await self.config.emoji_log_channel.set(None)
            await ctx.send(f"Emoji log channel unset.")
        else:
            await self.config.emoji_log_channel.set(channel.id)
            await ctx.send(f"Emoji log channel set to {channel.mention}.")

    @commands.command()
    @checks.bot_has_permissions(manage_emojis=True)
    @commands.is_owner()
    async def set_emoji_guild(self, ctx: commands.Context):
        if ctx.message.guild is None:
            await self.config.emoji_guild.set(None)
            await ctx.send(f"Emoji guild unset.")
        else:
            await self.config.emoji_guild.set(ctx.message.guild.id)
            await ctx.send(f"Emoji guild set to current guild.")

    async def emoji_guild(self):
        guild_id = await self.config.emoji_guild()
        if guild_id is None:
            return None
        return self.bot.get_guild(guild_id)

    async def emoji_log(self):
        channel_id = await self.config.emoji_log_channel()
        if channel_id is None:
            return None
        return self.bot.get_channel(channel_id)

    def is_gif(self, data: bytes):
        return data.startswith(self.GIF_HEADER)

    async def steal_emoji(self, name, url):
        emoji_guild = await self.emoji_guild()
        if emoji_guild is None:
            return None
        emoji_log = await self.emoji_log()
        image_data = requests.get(url).content
        animated = self.is_gif(image_data)
        if not image_data:
            return None
        try:
            result = await emoji_guild.create_custom_emoji(name=name, image=image_data)
        except discord.errors.HTTPException as e:
            for emoji in emoji_guild.emojis:
                if emoji.animated == animated:
                    if emoji_log:
                        await emoji_log.send(f"Deleting emoji {emoji} to make space")
                    await emoji.delete()
                    break
            result = await emoji_guild.create_custom_emoji(name=name, image=image_data)
        if emoji_log:
            if result:
                await emoji_log.send(f"Stolen emoji {result}")
            else:
                await emoji_log.send(
                    f"Failed to steal emoji {name} {id}{' (animated)' if animated else ''}"
                )
        return result

    async def add_url(self, name, url):
        async with self.config.custom("stealable_emoji", name).urls() as urls:
            if not any(u == url for u, _ in urls):
                usable = "discordapp" in url
                urls.append((url, usable))
                return True
        return False

    async def mark_url_unusable(self, name, url):
        async with self.config.custom("stealable_emoji", name).urls() as urls:
            for i, url_data in enumerate(urls):
                u, usable = url_data
                if u == url:
                    urls[i] = (u, False)
                    break

    def discord_emoji_url(self, id, anim):
        return f"https://cdn.discordapp.com/emojis/{id}.{'gif' if anim else 'png'}"

    def discord_emoji_from_url(self, url, name):
        match = re.match(
            r"https?://cdn\.discordapp\.com/emojis/([0-9]*)\.(gif|png)", url
        )
        if not match:
            return None
        return f"<{'a' if match.group(2) == 'gif' else ''}:{name}:{match.group(1)}>"

    @commands.command()
    @commands.is_owner()
    async def purge_emoji(self, ctx: commands.Context, emoji: str):
        await self.config.custom("stealable_emoji", emoji).clear()
        await ctx.message.add_reaction("\N{White Heavy Check Mark}")

    @commands.command()
    @commands.is_owner()
    async def save_usable_emoji(self, ctx: commands.Context):
        async with ctx.typing():
            count = 0
            for emoji in self.bot.emojis:
                count += await self.add_url(emoji.name, str(emoji.url))
        await ctx.send(f"New emoji found: {count}")

    @cog_slash(
        name="emojitext",
        description="Replaces emoji text in the given text by actual emoji",
    )
    async def emojitext(self, ctx: SlashContext, text: str):
        is_admin = ctx.author.permissions_in(ctx.channel).manage_messages
        for anim, name, id in re.findall(self.EMOJI_REGEX, text):
            id = int(id)
            url = self.discord_emoji_url(id, anim)
            await self.add_url(name, url)

        async def emoji_replace(emoji_name):
            stealable_urls = await self.config.custom(
                "stealable_emoji", emoji_name
            ).urls()
            emoji_strings = [
                (self.discord_emoji_from_url(url, emoji_name), url)
                for url, usable in stealable_urls
                if usable
            ]
            if emoji_strings:
                return random.choice(emoji_strings)[0]
            else:
                return f":{emoji_name}:"

        parts = re.split(r"(?:<a?)?:([0-9a-zA-Z_-]+):(?:[0-9]+>)?", text)
        for i, word in enumerate(parts):
            if i % 2 == 1:
                parts[i] = await emoji_replace(word)
        response = "".join(parts)
        response = response.lstrip(";?.!]")
        await ctx.send(response, allowed_mentions=discord.AllowedMentions.none())

    @cog_slash(name="emoji", description="Posts an emoji with a given name.")
    async def emoji(self, ctx: SlashContext, emoji_name: str):
        try:
            emoji_guild = await self.emoji_guild()
            if emoji_name[0] == "<":
                anim, name, id = re.match(self.EMOJI_REGEX, emoji_name).groups()
                id = int(id)
                # it turns out that discord grants us access to users'lemoji when in slash command context! lol
                # for emoji in self.bot.emojis:
                #    if emoji.available and (emoji.id == id or emoji.name == name):
                #        return await ctx.send(emoji_name)
                url = self.discord_emoji_url(id, anim)
                emoji = self.discord_emoji_from_url(url, name)
                await ctx.send(emoji)
                await self.add_url(name, url)
                return
                # emoji = await self.steal_emoji(name, url)
                # if emoji:
                #    return await ctx.send(str(emoji))
                # else:
                #    return
            emoji_name = emoji_name.strip(":")
            for emoji in self.bot.emojis:
                if emoji.name == emoji_name:
                    if emoji.guild != emoji_guild:
                        await self.add_url(emoji_name, str(emoji.url))
                    if emoji.available:
                        return await ctx.send(str(emoji))
            stealable_urls = await self.config.custom(
                "stealable_emoji", emoji_name
            ).urls()
            emoji_strings = [
                (self.discord_emoji_from_url(url, emoji_name), url)
                for url, usable in stealable_urls
                if usable
            ]

            message_to_edit = None
            if len(emoji_strings) > 0:
                random.shuffle(emoji_strings)
                for emoji_string, url in emoji_strings:
                    if message_to_edit is not None:
                        # await message_to_edit.edit(content=emoji_string)
                        new_msg = await ctx.send(emoji_string)
                        await message_to_edit.delete()
                        message_to_edit = new_msg
                    else:
                        message_to_edit = await ctx.send(emoji_string)
                    if "<" in message_to_edit.content:
                        return
                    else:
                        await self.mark_url_unusable(emoji_name, url)

            if len(stealable_urls) > 0:
                # await ctx.defer()
                emoji = await self.steal_emoji(
                    emoji_name, random.choice(stealable_urls)[0]
                )
                if emoji:
                    if message_to_edit is not None:
                        return await message_to_edit.edit(content=str(emoji))
                    else:
                        return await ctx.send(str(emoji))

            if self.bttv_enabled:
                # await ctx.defer()
                data = requests.get(
                    f"https://api.betterttv.net/3/emotes/shared/search?query={emoji_name}&offset=0&limit=50"
                ).json()
                for emoji in data:
                    name = emoji["code"]
                    if name == emoji_name:
                        url = f"https://cdn.betterttv.net/emote/{emoji['id']}/3x"
                        await self.add_url(emoji_name, url)
                stealable_urls = await self.config.custom(
                    "stealable_emoji", emoji_name
                ).urls()
                if stealable_urls:
                    emoji = await self.steal_emoji(
                        emoji_name, random.choice(stealable_urls)[0]
                    )
                    if emoji:
                        return await ctx.send(str(emoji))

            if message_to_edit is not None:
                return await message_to_edit.edit(content="No emoji found")
            else:
                return await ctx.send("No emoji found", hidden=True)
        except:
            import traceback

            return await self.bot.send_to_owners(traceback.format_exc())
            return

    @commands.command()
    @commands.is_owner()
    async def snoop_for_emoji(
        self, ctx: commands.Context, msg: discord.Message, limit=100
    ):
        found_count = 0
        async with ctx.typing():
            async for message in msg.channel.history(before=msg, limit=limit):
                found_count += await self.scan_for_emoji(message)
        await ctx.send(f"New emoji found: {found_count}")

    async def scan_for_emoji(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return 0
        found_count = 0
        for anim, name, id in re.findall(self.EMOJI_REGEX, message.content):
            url = self.discord_emoji_url(id, anim)
            found_count += await self.add_url(name, url)
        return found_count

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.scan_for_emoji(message)

    def normalize_name(self, name):
        return "".join(c for c in name.lower() if c.isalpha())

    @commands.command()
    async def emojisearch(self, ctx: commands.Context, searched_name: str):
        """Searches through known custom emojis."""
        emoji_data = (await self.config.custom("stealable_emoji").all()).items()
        searched_name = self.normalize_name(searched_name)
        embed_colour = await (
            ctx.embed_colour()
            if hasattr(ctx, "embed_colour")
            else self.bot.get_embed_colour(ctx.channel)
        )
        embeds = []
        for name, data in emoji_data:
            if searched_name in self.normalize_name(name):
                for url, usable in data["urls"]:
                    embed = discord.Embed(colour=embed_colour, title=name)
                    embed.set_image(url=url)
                    embeds.append(embed)
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"{i+1}/{len(embeds)}")
        if len(embeds) > 1:
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)
        elif len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await ctx.send("No results found \N{Pensive Face}")

    async def reroll_emoji(
        self,
        ctx: commands.Context,
        pages: list,
        controls: dict,
        message: discord.Message,
        page: int,
        timeout: float,
        emoji: str,
    ):
        perms = message.channel.permissions_for(ctx.me)
        if perms.manage_messages:  # Can manage messages, so remove react
            with contextlib.suppress(discord.NotFound):
                await message.remove_reaction(emoji, ctx.author)
        emoji_data = list((await self.config.custom("stealable_emoji").all()).items())
        name, data = random.choice(emoji_data)
        embed_colour = await (
            ctx.embed_colour()
            if hasattr(ctx, "embed_colour")
            else self.bot.get_embed_colour(ctx.channel)
        )
        embed = discord.Embed(colour=embed_colour, title=name)
        embed.set_image(url=random.choice(data["urls"])[0])
        return await menu(
            ctx, [embed], controls, message=message, page=page, timeout=timeout
        )

    async def close_menu(
        self,
        ctx: commands.Context,
        pages: list,
        controls: dict,
        message: discord.Message,
        page: int,
        timeout: float,
        emoji: str,
    ):
        with contextlib.suppress(discord.NotFound):
            await message.delete()

    @commands.command()
    async def randomemoji(self, ctx: commands.Context):
        """Responds with a random known custom emoji picture."""
        emoji_data = list((await self.config.custom("stealable_emoji").all()).items())
        name, data = random.choice(emoji_data)
        embed_colour = await (
            ctx.embed_colour()
            if hasattr(ctx, "embed_colour")
            else self.bot.get_embed_colour(ctx.channel)
        )
        embed = discord.Embed(colour=embed_colour, title=name)
        embed.set_image(url=random.choice(data["urls"])[0])

        controls = {
            "\N{Anticlockwise Downwards and Upwards Open Circle Arrows}": self.reroll_emoji,
            "\N{CROSS MARK}": self.close_menu,
        }
        await menu(ctx, [embed], controls, timeout=15.0)

    @commands.command()
    @commands.is_owner()
    async def allemoji(self, ctx: commands.Context):
        html = [
            "<style>body{background:#333}div{display:inline-block;background:#222;color:#eee;font-family:Arial;width:200px;height:220px;margin:10px}img{height:200px;width:200px}</style>"
        ]
        for name, data in (await self.config.custom("stealable_emoji").all()).items():
            if "urls" not in data:
                continue
            for url, usable in data["urls"]:
                html.append(f"<div><img src='{url}'><br><center>{name}</center></div>")
        html = "".join(html)
        await ctx.send(files=[discord.File(io.StringIO(html), "emoji.html")])
