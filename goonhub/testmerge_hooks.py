from fastapi import FastAPI
from pydantic import BaseModel
from typing import *

class TestmergeChangeModel(BaseModel):
    api_key: str
    pr: int
    servers: list[str]
    commit: Optional[str] = ''

class TestmergeHooks():
    def __init__(self, config, Goonhub, app: FastAPI):
        self.config = config
        self.Goonhub = Goonhub
        self.app = app

        @app.post("/testmerges/added")
        async def added(data: TestmergeChangeModel):
            if await self.Goonhub.check_incoming_key(data.api_key) == False: return
            await self.announce(data, "\N{White Heavy Check Mark} **New** testmerge\n")
            
        @app.post("/testmerges/updated")
        async def updated(data: TestmergeChangeModel):
            if await self.Goonhub.check_incoming_key(data.api_key) == False: return
            await self.announce(data, "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} **Updated** testmerge\n")
            
        @app.post("/testmerges/removed")
        async def removed(data: TestmergeChangeModel):
            if await self.Goonhub.check_incoming_key(data.api_key) == False: return
            await self.announce(data, "\N{CROSS MARK} **Cancelled** testmerge\n")
                    
    async def announce(self, data: TestmergeChangeModel, msg: str):
        channels = await self.config.testmerge_channels()
        if not len(channels): return
        repo = await self.Goonhub.config.repo()
        commit = data.commit.strip() if data.commit else ''
        
        msg += f"https://github.com/{repo}/pull/{data.pr}\n"
        if commit:
            msg += f"on commit https://github.com/{repo}/pull/{data.pr}/commits/{commit}\n"
        if len(data.servers):
            msg += "on servers "
            for server in data.servers:
                msg += server + " "
        for channel_id in channels:
            channel = self.Goonhub.bot.get_channel(int(channel_id))
            if channel:
                await channel.send(msg)