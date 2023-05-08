import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
import json
import re
import time
import io
import datetime
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response
from concurrent.futures.thread import ThreadPoolExecutor
import yt_dlp
import base64
from PIL import Image

class SpacebeeCommands(commands.Cog):
    FILE_SIZE_LIMIT = 15 * 1024 * 1024

    def __init__(self, bot: Red):
        self.bot = bot
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.last_profiler_check_message = None
        self.last_profiler_id = None

    def register_to_general_api(self, app):
        @app.post("/profiler_result", response_class=Response)
        async def profiler_result(request: Request):
            if self.last_profiler_check_message is None:
                return
            dat_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            prof_file = discord.File(
                io.BytesIO(await request.body()),
                filename=f"profiling_{self.last_profiler_id}_{dat_string}.json",
            )
            msg = "Consider using https://mini.xkeeper.net/ss13/profiler/ to view the results:"
            await self.last_profiler_check_message.reply(msg, file=prof_file)
            self.last_profiler_check_message = None
            return "ok"

    def format_whois(self, response):
        count = int(response["count"])
        out = []
        for i in range(1, count + 1):
            rolestuff = response.get(f"role{i}", "jobless")
            if response.get(f"dead{i}"):
                rolestuff += " DEAD"
            if response.get(f"t{i}"):
                rolestuff += " \N{REGIONAL INDICATOR SYMBOL LETTER T}"
            line = (
                response.get(f"name{i}", "-")
                + " ("
                + response.get(f"ckey{i}", "-")
                + ") "
                + rolestuff
            )
            out.append(line)
        if out:
            return "\n".join(out)
        return "No one found."

    def ckeyify(self, text):
        return "".join(c.lower() for c in text if c.isalnum())

    @commands.command()
    @checks.admin()
    async def locate(self, ctx: commands.Context, *, who: str):
        """Locates a ckey on all servers."""
        who = self.ckeyify(who)
        goonservers = self.bot.get_cog("GoonServers")
        servers = [s for s in goonservers.servers if s.type == "goon"]
        futures = [
            asyncio.Task(goonservers.send_to_server(s, "status", to_dict=True))
            for s in servers
        ]
        message = None
        done, pending = [], futures
        old_text = None
        while pending:
            when = asyncio.FIRST_COMPLETED if message else asyncio.ALL_COMPLETED
            done, pending = await asyncio.wait(pending, timeout=0.2, return_when=when)
            if not done:
                continue
            lines = []
            for server, f in zip(servers, futures):
                if f.done() and f.exception() is None:
                    result = f.result()
                    server_found = []
                    for k, v in result.items():
                        if k.startswith("player") and who in self.ckeyify(v):
                            server_found.append(v)
                    if not server_found:
                        continue
                    if len(server_found) == 1:
                        lines.append(f"{server.full_name}: **{server_found[0]}**")
                    else:
                        lines.append(f"{server.full_name}:")
                        lines.extend(f"\t**{p}**" for p in server_found)
            if not lines:
                continue
            text = "\n".join(lines)
            if len(text) > 2000:
                text = text[:1900] + "\n[Message too long, shorten your query]"
            if message is None:
                message = await ctx.send(text)
            elif text != old_text:
                await message.edit(content=text)
            old_text = text
        if not message:
            await ctx.send("No one found.")

    @commands.command()
    @checks.admin()
    async def whois(self, ctx: commands.Context, server_id: str, *, query: str):
        """Looks for a person on a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "whois",
                "target": query,
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        for page in pagify(self.format_whois(response)):
            await ctx.send(page)

    @commands.command()
    async def players(self, ctx: commands.Context, server_id: str):
        """Lists players on a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id, "status", ctx.message, to_dict=True
        )
        if response is None:
            return
        players = []
        try:
            for i in range(int(response["players"])):
                players.append(response[f"player{i}"])
        except KeyError:
            await ctx.message.reply("That server is not responding correctly.")
            return
        players.sort()
        if players:
            await ctx.message.reply(", ".join(players))
        else:
            await ctx.message.reply("No players.")

    @commands.command()
    @checks.admin()
    async def ooc(self, ctx: commands.Context, server_id: str, *, message: str):
        """Sends an OOC message to a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "ooc",
                "msg": message,
                "nick": f"(Discord) {ctx.author.name}",
            },
            ctx.message,
            react_success=True,
        )

    @commands.command()
    @checks.admin()
    async def antags(self, ctx: commands.Context, server_id: str):
        """Lists antagonists on a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "antags",
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        for page in pagify(self.format_whois(response)):
            await ctx.send(page)

    @commands.command()
    @checks.admin()
    async def ailaws(self, ctx: commands.Context, server_id: str):
        """Lists current AI laws on a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "ailaws",
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        if response == 0.0:
            await ctx.send("Round hasn't started yet.")
            return
        out = response['laws']
        if isinstance(out, str):
            if out:
                await ctx.send(out)
            else:
                await ctx.send("No law racks with connected silicons.")
        else:
            await ctx.send("Law data recieved in wrong format.")

    @commands.command(aliases=["hcheck"])
    @checks.admin()
    async def scheck(self, ctx: commands.Context, server_id: str):
        """Checks server health of a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "health",
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        start_time = time.time()
        await goonservers.send_to_server_safe(server_id, "status", ctx)
        elapsed = time.time() - start_time
        if response is None:
            return
        out = f"""CPU: {response['cpu']}
time scaling: {response['time']}
ticklag: {response.get('ticklag', 'N/A')}
runtimes: {response.get('runtimes', 'N/A')}
RTT: {elapsed * 1000:.2f}ms"""
        if "meminfo" in response:
            out += f"\n```{response['meminfo']}```"
        await ctx.send(out)

    @commands.command()
    @checks.admin()
    async def rev(self, ctx: commands.Context, server_id: str):
        """Checks code revision of a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "rev",
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        rev, author = response["msg"].split(" by ")
        await ctx.send(
            response["msg"]
            + "\nhttps://github.com/goonstation/goonstation/commit/"
            + rev
        )

    @commands.command()
    @checks.admin()
    async def version(self, ctx: commands.Context, server_id: str):
        """Checks BYOND version of a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "version",
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.send(
            f"BYOND {response['major']}.{response['minor']}\nGoonhub: {response['goonhub_api']}"
        )

    @commands.command()
    @checks.admin()
    async def delay(self, ctx: commands.Context, server_id: str):
        """Delays a Goonstation round end."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "delay",
                "nick": ctx.message.author.name,
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.send(response["msg"])

    @commands.command()
    @checks.admin()
    async def undelay(self, ctx: commands.Context, server_id: str):
        """Undelays a Goonstation round end."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "undelay",
                "nick": ctx.message.author.name,
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.send(response["msg"])

    @commands.command()
    @checks.is_owner()
    async def rickroll(self, ctx: commands.Context, server_id: str):
        """Test command to check if playing music works."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "youtube",
                "data": '{"key":"Pali6","title":"test","duration":4,"file":"https://qoret.com/dl/uploads/2019/07/Rick_Astley_-_Never_Gonna_Give_You_Up_Qoret.com.mp3"}',
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.message.add_reaction("\N{FROG FACE}")

    async def youtube_play(self, ctx, url, server_id):
        generalapi = self.bot.get_cog("GeneralApi")
        file_folder = generalapi.static_path / "youtube"
        file_folder.mkdir(exist_ok=True)
        file_name = url
        if "watch?v=" in file_name:
            file_name = file_name.split("watch?v=")[1]
        else:
            file_name = self.ckeyify(file_name)
        tmp_file_name = file_name + ".webm"
        play_file_name = file_name + ".webm.mp3"
        tmp_file_path = file_folder / tmp_file_name
        play_file_path = file_folder / play_file_name
        info = None
        if not play_file_path.is_file():
            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "8",
                    "nopostoverwrites": False,
                }
            ]
            ydl_opts = {
                "format": "worstaudio/worst",
                "geo_bypass": True,
                "outtmpl": str(tmp_file_path),
                "postprocessors": postprocessors,
                "max_filesize": self.FILE_SIZE_LIMIT,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                filesize = min(
                    fmt["filesize"]
                    for fmt in info["formats"]
                    if isinstance(fmt.get("filesize"), int)
                )
                if filesize > self.FILE_SIZE_LIMIT:
                    return None
                await asyncio.get_running_loop().run_in_executor(
                    self.executor, ydl.download, [url]
                )
        if not play_file_path.is_file():
            return None
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "youtube",
                "data": json.dumps(
                    {
                        "key": ctx.message.author.name + " (Discord)",
                        "file": f"https://medass.pali.link/static/youtube/{play_file_name}",
                        "duration": "?",
                        "title": info["title"] if info else file_name,
                    }
                ),
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return None
        return True

    @commands.command()
    @checks.admin()
    async def remotemusic(
        self, ctx: commands.Context, server_id: str, link: Optional[str]
    ):
        """Attach a file to the command message and it plays on a given Goonstation server."""
        if len(ctx.message.attachments) == 0 and link is None:
            await ctx.send(
                "You need to attach a sound file to your message or provide a link."
            )
            return
        if link is not None and ("youtube.com" in link or "youtu.be" in link):
            response = None
            async with ctx.typing():
                try:
                    response = await self.youtube_play(ctx, link, server_id)
                except yt_dlp.utils.DownloadError as e:
                    await ctx.send("YoutubeDL error: " + str(e))
                    return
            if response:
                await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            else:
                await ctx.send("something went wrong")
            return
        url = link
        filename = link
        if len(ctx.message.attachments) > 0:
            url = ctx.message.attachments[0].url
            filename = ctx.message.attachments[0].filename
        if not filename.endswith("mp3") and not filename.endswith("m4a"):
            await ctx.send(
                "That's not an mp3 nor an m4a file so it'll likely not work. But gonna try anyway."
            )
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "youtube",
                "data": json.dumps(
                    {
                        "key": ctx.message.author.name + " (Discord)",
                        "file": url,
                        "duration": "?",
                        "title": filename,
                    }
                ),
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    @checks.admin()
    async def medspeech(self, ctx: commands.Context, server_id: str, *, text: str):
        """Speech synthesis on a given Goonstation server."""
        generalapi = self.bot.get_cog("GeneralApi")
        speech_folder = generalapi.static_path / "speech"
        speech_folder.mkdir(exist_ok=True)
        file_name = f"{self.ckeyify(text)[:128]}.mp3"
        file_path = speech_folder / file_name
        if not file_path.is_file():
            p = await asyncio.create_subprocess_shell(
                "text2wave -scale 3 | ffmpeg -i - -vn -ar 44100 -ac 2 -b:a 64k "
                + str(file_path),
                stdin=asyncio.subprocess.PIPE,
            )
            await p.communicate(text.encode("utf8"))
        if not file_path.is_file():
            await ctx.send("Could not generate sound.")
            return
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "youtube",
                "data": json.dumps(
                    {
                        "key": ctx.message.author.name + " (Discord)",
                        "file": f"http://medass.pali.link/static/speech/{file_name}",
                        "duration": "?",
                        "title": text,
                    }
                ),
            },
            ctx,
            to_dict=True,
        )
        if response is None:
            return
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @commands.command()
    @checks.admin()
    async def admins(self, ctx: commands.Context, server_id: str):
        """Lists admins in a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id, "admins", ctx.message, to_dict=True
        )
        if response is None:
            return
        admins = []
        try:
            for i in range(int(response["admins"])):
                admin = response[f"admin{i}"]
                if admin.startswith("~"):
                    continue
                admins.append(admin)
        except KeyError:
            await ctx.message.reply("That server is not responding correctly.")
            return
        admins.sort()
        if admins:
            await ctx.message.reply(", ".join(admins))
        else:
            await ctx.message.reply("No admins.")

    @commands.command()
    @checks.admin()
    async def mentors(self, ctx: commands.Context, server_id: str):
        """Lists mentors in a given Goonstation server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id, "mentors", ctx.message, to_dict=True
        )
        if response is None:
            return
        mentors = []
        try:
            for i in range(int(response["mentors"])):
                mentor = response[f"mentor{i}"]
                mentors.append(mentor)
        except KeyError:
            await ctx.message.reply("That server is not responding correctly.")
            return
        mentors.sort()
        if mentors:
            await ctx.message.reply(", ".join(mentors))
        else:
            await ctx.message.reply("No mentors.")

    @commands.command()
    @commands.cooldown(1, 1)
    @commands.max_concurrency(1, wait=True)
    async def stats(
        self, ctx: commands.Context, *, ckey: Optional[Union[discord.User, str]]
    ):
        """Shows playtime stats of a given ckey (or yours if no ckey given)."""
        await self._stats(ctx=ctx, ckey=ckey, admin=False)

    @checks.admin()
    @commands.command()
    async def statsadmin(
        self, ctx: commands.Context, *, ckey: Optional[Union[discord.User, str]]
    ):
        """Shows all kinds of stats of a given ckey (or yours if no ckey given)."""
        await self._stats(ctx=ctx, ckey=ckey, admin=True)

    async def _stats(
        self, ctx: commands.Context, *, ckey: Optional[Union[discord.User, str]], admin=False
    ):
        goonservers = self.bot.get_cog("GoonServers")
        if ckey is None:
            ckey = ctx.author
        if isinstance(ckey, str):
            ckey = self.ckeyify(ckey)
        else:
            spacebeecentcom = self.bot.get_cog("SpacebeeCentcom")
            ckey = await spacebeecentcom.user_to_ckey(ckey)
            if not ckey:
                message_parts = ctx.message.content.split(" ", 1)
                maybe_ckey = message_parts[1] if len(message_parts) >= 2 else None
                if maybe_ckey and maybe_ckey[0] != "<":
                    ckey = maybe_ckey
                else:
                    await ctx.message.reply("That user has no BYOND account linked")
                    return
        response = await goonservers.send_to_server_safe(
            "1", {"type": "getPlayerStats", "ckey": ckey}, ctx.message
        )
        if response is None:
            return
        if response == 0:
            await ctx.message.reply("Could not load stats.")
            return
        data = json.loads(response)
        if isinstance(data, dict) and data.get("error"):
            await ctx.message.reply("Error: " + data["error"])
            return
        embed_colour = await ctx.embed_colour()
        embed = discord.Embed(
            title=f"Stats of `{ckey}`",
            timestamp=ctx.message.created_at,
            color=embed_colour,
        )
        embed.add_field(name="rounds (total)", value=data.pop("seen"))
        embed.add_field(name="rounds (rp)", value=data.pop("seen_rp"))
        embed.add_field(name="rounds joined (total)", value=data.pop("participated"))
        embed.add_field(name="rounds joined (rp)", value=data.pop("participated_rp"))
        if "playtime" in data:
            playtime_seconds = int(json.loads(data["playtime"])[0]["time_played"])
            data.pop("playtime")
            time_played = goonservers.seconds_to_hhmmss(playtime_seconds)
            embed.add_field(name="time played", value=time_played)
        if admin:
            last_seen_data = data.pop("last_seen")
            last_seen_str = "No last seen data, run command again"
            if isinstance(last_seen_data, str):
                last_seen = datetime.datetime.fromisoformat(last_seen_data)
                timestamp = int(last_seen.timestamp())
                last_seen_str = f"<t:{timestamp}:F> (<t:{timestamp}:R>)"
            embed.add_field(name="last seen", value=last_seen_str)
            for key, value in data.items():
                if key == "cloudsaves":
                    if isinstance(value, dict):
                        value = value.keys()
                    value = ", ".join(value)
                if not value:
                    continue
                embed.add_field(name=key, value=str(value))
        await ctx.send(embed=embed)

    @commands.group(name="profiler")
    @checks.admin()
    async def profiler(self, ctx: commands.Context):
        """Profile a game server."""
        pass

    @profiler.command(name="start")
    async def profiler_start(
        self, ctx: commands.Context, server_id: str, type: Optional[str]
    ):
        """Starts the profiler on a given server.

        type argument can be `sendmaps` per byond reference."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "start",
                "profiler_type": type,
            },
            ctx,
        )
        if response is None:
            return
        if response == 1:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await ctx.send("Unknown error.")

    @profiler.command(name="stop")
    async def profiler_stop(
        self, ctx: commands.Context, server_id: str, type: Optional[str]
    ):
        """Stops the profiler on a given server, returns output."""
        goonservers = self.bot.get_cog("GoonServers")
        self.last_profiler_check_message = ctx.message
        self.last_profiler_id = server_id
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "stop",
                "profiler_type": type,
            },
            ctx,
        )
        if response is None:
            return
        if response == 1:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await ctx.send("Unknown error.")
        # dat_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # prof_file = discord.File(io.StringIO(response), filename=f"profiling_{server_id}_{dat_string}.json")
        # await ctx.send(file=prof_file)

    @profiler.command(name="clear")
    async def profiler_clear(
        self, ctx: commands.Context, server_id: str, type: Optional[str]
    ):
        """Clears the profiler stats on a given server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "clear",
                "profiler_type": type,
            },
            ctx,
        )
        if response is None:
            return
        if response == 1:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await ctx.send("Unknown error.")

    @profiler.command(name="restart")
    async def profiler_restart(
        self, ctx: commands.Context, server_id: str, type: Optional[str]
    ):
        """Restarts the profiler on a given server."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "restart",
                "profiler_type": type,
            },
            ctx,
        )
        if response is None:
            return
        if response == 1:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await ctx.send("Unknown error.")

    @profiler.command(name="save")
    async def profiler_save(
        self,
        ctx: commands.Context,
        server_id: str,
        type: Optional[str],
        average: Optional[int],
    ):
        """Saves current profiling data to the server's logs folder."""
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "save",
                "profiler_type": type,
            },
            ctx,
        )
        if response is None:
            return
        await ctx.send(
            f"Profiling result saved in `{response}`. Consider using https://mini.xkeeper.net/ss13/profiler/ to view the results."
        )

    @profiler.command(name="get", aliases=["check"])
    async def profiler_get(
        self,
        ctx: commands.Context,
        server_id: str,
        type: Optional[str],
        average: Optional[int],
    ):
        """Fetches and returns current profiling data of a server."""
        goonservers = self.bot.get_cog("GoonServers")
        self.last_profiler_check_message = ctx.message
        self.last_profiler_id = server_id
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "profile",
                "action": "refresh",
                "profiler_type": type,
                "average": average,
            },
            ctx,
        )
        if response is None:
            return
        if response == 1:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await ctx.send("Unknown error.")
        # dat_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # prof_file = discord.File(io.StringIO(response), filename=f"profiling_{server_id}_{dat_string}.json")
        # await ctx.send(file=prof_file)

    @commands.command()
    @checks.admin()
    async def canvas(self, ctx: commands.Context, server_id: str, *, canvas_name: str = 'centcom'):
        goonservers = self.bot.get_cog("GoonServers")
        request = {"type": "persistent_canvases"}
        if canvas_name != 'centcom':
            request = {"type": "lazy_canvas_get", "id": canvas_name}
        response = await goonservers.send_to_server_safe(
            server_id,
            request,
            ctx,
            to_dict=False,
        )
        if response is None:
            return
        data = json.loads(response)
        if not isinstance(data, dict) or canvas_name not in data:
            await ctx.send(f"Canvas not found. Run `]canvas_list {server_id}` to see existing canvases.")
            return
        data = base64.b64decode(data[canvas_name])
        img_file = discord.File(io.BytesIO(data), filename="canvas.png")
        await ctx.send(file=img_file)

    @commands.command()
    @checks.admin()
    async def canvaslist(self, ctx: commands.Context, server_id: str):
        goonservers = self.bot.get_cog("GoonServers")
        response = await goonservers.send_to_server_safe(
            server_id,
            {
                "type": "lazy_canvas_list",
            },
            ctx,
            to_dict=False,
        )
        if response is None:
            return
        canvases = json.loads(response)
        if len(canvases):
            await ctx.send(", ".join(canvases))
        else:
            await ctx.send("No canvases")
