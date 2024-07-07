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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from uvicorn import Server, Config
from redbot.core.data_manager import cog_data_path, bundled_data_path
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging


class GeneralApi(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.server = None
        self.config = redbot.core.Config.get_conf(self, identifier=563126567942)
        self.config.register_global(
            port=None,
            host="0.0.0.0",
        )

        self.app = FastAPI()

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        static_path = cog_data_path(self) / "static"
        static_path.mkdir(parents=True, exist_ok=True)
        self.static_path = static_path

        self.rebuild_api_paths()

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
            logging.error("422 Unprocessable entitity: " + exc_str)
            content = {'status_code': 10422, 'message': exc_str, 'data': None}
            return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    def rebuild_api_paths(self):
        self.app.router.routes.clear()
        for cog in self.bot.cogs.values():
            if hasattr(cog, "register_to_general_api"):
                cog.register_to_general_api(self.app)
        self.sf = StaticFiles(directory=str(self.static_path))
        self.app.mount("/static", self.sf, name="static")

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
        if self.server:
            del self.server
        self.server = Server(self.uvi_config)
        asyncio.ensure_future(self.start_api_server())

    def cog_unload(self):
        self.server.should_exit = True

    @commands.Cog.listener()
    async def on_cog_add(self, cog: commands.Cog) -> None:
        if hasattr(cog, "register_to_general_api"):
            #cog.register_to_general_api(self.app)
            self.rebuild_api_paths()
            self.app.openapi_schema = None
            # self.server.should_exit = True
            # self.init_app()
            #await self.init()
