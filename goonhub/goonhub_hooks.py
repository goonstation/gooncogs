from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import *

GUILD_ID = 182249960895545344
ADMIN_ID = 182250010769883137
MENTOR_ID = 182266829392183296
HOS_ID = 576994272822165515
PLAYER_ID = 182284445837950977

class GoonhubHooks():
    def __init__(self, config, Goonhub, app: FastAPI):
        self.config = config
        self.Goonhub = Goonhub
        self.app = app

        @app.get("/goonhub/auth")
        async def auth(api_key: str, discord_id: int):
            if await self.Goonhub.check_incoming_key(api_key) == False: return
            spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
            guild = self.Goonhub.bot.get_guild(GUILD_ID)
            try:
                member = guild.get_member(discord_id)
            except:
                return {"status": "error", "response": "Invalid Discord ID"}

            if member:
                ckey = await spacebeecentcom.config.user(member).linked_ckey()
            else:
                return {"status": "error", "response": "Discord member not found"}

            return {
                "status": "ok",
                "ckey": ckey,
                "is_admin": True if member.get_role(ADMIN_ID) is not None else False,
                "is_mentor": True if member.get_role(MENTOR_ID) is not None else False,
                "is_hos": True if member.get_role(HOS_ID) is not None else False,
                "is_player": True if member.get_role(PLAYER_ID) is not None else False,
            }

        @app.get("/goonhub/all_links")
        async def all_links(api_key: str):
            if await self.Goonhub.check_incoming_key(api_key) == False: return
            spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
            all_links = await spacebeecentcom.config.custom("ckey").all()
            return {
                "status": "ok",
                "links": all_links,
            }
