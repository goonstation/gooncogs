import discord
import re
import asyncio
import aiohttp
import os
import subprocess
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from concurrent.futures.thread import ThreadPoolExecutor
import youtube_dl

class LoudVideos(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.CHUNK_SIZE = 100 * 1024
        self.FILE_SIZE_LIMIT = 15 * 1024 * 1024
        self.debug = False

    @commands.command()
    @commands.is_owner()
    async def toggle_loudvideo_debug(self, ctx: commands.Context):
        self.debug = not self.debug
        await ctx.send(f"Debug set to: {self.debug}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.embeds and after.embeds:
            await self.check_message(after)

    async def check_message(self, message: discord.Message):
        file_path = None
        try:
            if message.guild is None or \
                await self.bot.cog_disabled_in_guild(self, message.guild) or \
                (not message.embeds and not message.attachments):
                return
            urls = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("video/"):
                    urls.append(attachment.url)
            for embed in message.embeds:
                if embed.video:
                    urls.append(embed.video.url)
            for url in urls:
                file_path = cog_data_path(self) / url.split('/')[-1]
                file_path = str(file_path).split('?')[0][:64]
                if "youtube" in url:
                    ydl_opts = {
                        'format': 'worst',
                        'outtmpl': str(file_path)
                    }
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        filesize = min(fmt["filesize"] for fmt in info["formats"] if isinstance(fmt["filesize"], int))
                        if filesize > self.FILE_SIZE_LIMIT:
                            if self.debug: await self.bot.send_to_owners(f"{url}\ntoo large {filesize}")
                            return
                        await asyncio.get_running_loop().run_in_executor(self.executor, ydl.download, [url])
                else:
                    filesize = 0
                    with open(file_path, 'wb') as fd:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as res:
                                while True:
                                    chunk = await res.content.read(self.CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    filesize += self.CHUNK_SIZE
                                    if filesize > self.FILE_SIZE_LIMIT:
                                        if self.debug: await self.bot.send_to_owners(f"{url}\ntoo large {filesize}")
                                        return
                                    fd.write(chunk)
                ffmpeg_output = subprocess.run(["ffmpeg", "-i", str(file_path), "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "/dev/null"], capture_output=True).stderr.decode("utf8")
                mean_volume_match = re.search("mean_volume: ([-0-9.]*) dB", ffmpeg_output)
                mean_volume = float(mean_volume_match.group(1)) if mean_volume_match else None 
                max_volume_match = re.search("max_volume: ([-0-9.]*) dB", ffmpeg_output)
                max_volume = float(max_volume_match.group(1)) if max_volume_match else None 
                if mean_volume is not None and mean_volume > -10.0:# or max_volume > 0:
                    await message.reply("\N{Warning Sign}This video might be very loud!\N{Warning Sign}", mention_author=False)
                if self.debug: await self.bot.send_to_owners(f"{url}\nmean volume: {mean_volume} dB\nmax volume: {max_volume} dB")
        finally:
            if file_path is not None:
                os.remove(file_path)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        await self.check_message(message)
