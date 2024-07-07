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
import io
from PIL import Image, ImageOps

# TARGET_CHANNEL = 412381738510319626
TARGET_CHANNEL = 606119557228396554

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

    def get_server(self, server_id):
        goonservers_cog = self.bot.get_cog("GoonServers")
        return goonservers_cog.resolve_server(server_id)

    async def server_dep(self, server: str, server_name: str, api_key: str):
        if api_key != (await self.bot.get_shared_api_tokens("spacebee"))["api_key"]:
            raise self.SpacebeeError("Invalid API key.", 403)
        server = self.get_server(server_name) or self.get_server(server)
        if server is None:
            raise self.SpacebeeError("Unknown server.", 404)
        return server

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
            cost = int(cost)
            artist = int(artist)
            tier = [i for i, x in enumerate([2500, 7500, 20000, 40000, float('inf')]) if x >= cost][0]
            tier_emoji = "\N{white small square}\N{small orange diamond}\N{white medium star}\N{glowing star}\N{gem stone}"
            tier_colors = [
                discord.Colour.from_rgb(70, 70, 70),
                discord.Colour.from_rgb(205, 127, 50),
                discord.Colour.from_rgb(192, 192, 192),
                discord.Colour.from_rgb(255, 215, 0),
                discord.Colour.from_rgb(140, 202, 247),
                ]
            emoji = tier_emoji[tier]
            channel = self.bot.get_channel(TARGET_CHANNEL)
            data = base64.b64decode(art)
            image = Image.open(io.BytesIO(data))
            image = ImageOps.scale(image, 6, resample=Image.Resampling.NEAREST)
            out_data = io.BytesIO()
            image.save(out_data, format="png")
            out_data.seek(0)
            file = discord.File(out_data, filename="art.png")
            embed_title = f"{emoji} {title} {emoji}"
            embed = discord.Embed()
            embed.colour = tier_colors[tier]
            embed.set_image(url="attachment://art.png")
            embed.title = embed_title
            embed.description = f"New gallery art on {server.full_name}!"
            by_whom = f"by {ckey} " if artist else ""
            embed.set_footer(text=f"{by_whom}in {exhibit} ({cost}$)")
            await channel.send(embed=embed, file=file)
            return self.SUCCESS_REPLY
