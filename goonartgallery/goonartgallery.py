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
from github import Github
import base64

TARGET_CHANNEL = 412381738510319626

class GoonArtGallery(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

    async def init(self):
        pass

    class SpacebeeError(Exception):
        def __init__(self, message: str, status_code: int, error_code: int = 0):
            self.message = message
            self.status_code = status_code
            self.error_code = error_code

    def register_to_general_api(self, app):
        @app.exception_handler(self.SpacebeeError)
        async def invalid_api_key_error_handler(
            request: Request, exc: self.SpacebeeError
        ):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "status": "error",
                    "errormsg": exc.message,
                    "error": exc.error_code,
                },
            )

        @app.get("/gallery")
        async def gallery(
                title: str, artist: str, ckey: str, exhibit: str, cost: str, art: str, server=Depends(self.server_dep)
        ):
            channel = self.bot.get_channel(TARGET_CHANNEL)
            data = base64.b64decode(art)
            file = discord.File(io.BytesIO(data), filename="art.png")
            emoji = ""
            embed_title = f"{emoji} {title} {emoji}"
            embed = discord.Embed()
            embed.set_image(url="attachment://art.png")
            embed.title = embed_title
            embed.description = f"New gallery art on {server.full_name}!"
            embed.set_footer(text=f"by {artist} in {exhibit} ({cost}$)")
            await channel.send(embed=embed, file=file)
            return self.SUCCESS_REPLY
