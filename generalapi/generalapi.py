import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, checks
import redbot.core
import discord.errors
from redbot.core.bot import Red
from typing import *
import re
import time
from fastapi import FastAPI, Request
from uvicorn import Server, Config
from redbot.core.data_manager import cog_data_path, bundled_data_path
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


class GeneralApi(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.app = FastAPI()

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.config = redbot.core.Config.get_conf(self, identifier=563126567942)
        self.config.register_global(
            port=None,
            host="0.0.0.0",
        )

        for cog in self.bot.cogs.values():
            if hasattr(cog, "register_to_general_api"):
                cog.register_to_general_api(self.app)

        static_path = cog_data_path(self) / "static"
        static_path.mkdir(parents=True, exist_ok=True)
        self.sf = StaticFiles(directory=str(cog_data_path(self) / "static"))
        self.app.mount("/static", self.sf, name="static")
        self.static_path = static_path

    @commands.command()
    @checks.is_owner()
    async def set_general_api(self, ctx: commands.Context, host: str, port: int):
        await self.config.host.set(host)
        await self.config.port.set(port)
        await ctx.send("Host and port set, reload the cog to apply changes.")

    async def start_api_server(self):
        tries_left = 5
        success = False
        while not success and tries_left > 0:
            tries_left -= 1
            success = True
            try:
                await self.server.serve()
            except SystemExit:
                success = False
                await asyncio.sleep(0.1)
        if not success:
            await self.bot.send_to_owners("FastAPI server failed to start")

    async def init(self):
        host = await self.config.host()
        port = await self.config.port()
        if not port:
            await self.bot.send_to_owners(
                "GeneralAPI host/port not set, use the set_general_api command and reload the cog."
            )
            return
        self.uvi_config = Config(app=self.app, host=host, port=port, log_level="debug")
        self.server = Server(self.uvi_config)
        asyncio.ensure_future(self.start_api_server())

    def cog_unload(self):
        self.server.should_exit = True

    @commands.Cog.listener()
    async def on_cog_add(self, cog: commands.Cog) -> None:
        if hasattr(cog, "register_to_general_api"):
            cog.register_to_general_api(self.app)
            self.app.openapi_schema = None
