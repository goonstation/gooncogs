import discord
from fastapi import FastAPI
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from pydantic import BaseModel
from typing import *
import logging

class ServerCrashModel(BaseModel):
    api_key: str
    server: str
    reason: Optional[str] = ''

class ServerCrashEndpoint(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 45632487954)
        self.config.register_global(channels={})
        
    def register_to_general_api(self, app: FastAPI):
        @app.post("/server_crash")
        async def server_crash(data: ServerCrashModel):
            tokens = await self.bot.get_shared_api_tokens("servercrashnotifier")
            if data.api_key != tokens["api_key"]: return
            channels = await self.config.channels()
            if not len(channels): return
            data.server = data.server.strip()
            goonservers = self.bot.get_cog("GoonServers")
            server = goonservers.resolve_server(data.server)
            desc = ""
            if data.reason:
                desc += f"Possible reason:\n```{data.reason}```\n"
            desc += f"[View Recent Errors](https://goonhub.com/admin/errors?filters[server_id]={data.server})"
            embed = discord.Embed(
                title = f"{server.short_name} Crashed!",
                description = desc,
                color = discord.Colour.from_str("#ff0000")
            )
            for channel_id in channels:
                channel = self.bot.get_channel(int(channel_id))
                await channel.send(embed=embed)
            
    @commands.hybrid_group(name="server-crashes")
    @checks.admin()
    async def scegroup(self, ctx: commands.Context):
        """Server Crash Notifier."""
        pass
    
    @scegroup.command()
    @checks.admin()
    async def addchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Subscribe a channel to receive server crash notifications."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            channels[str(channel.id)] = None
        await ctx.reply(
            f"Channel {channel.mention} will now receive notifications about server crashes."
        )

    @scegroup.command()
    @checks.admin()
    async def removechannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Unsubscribe a channel from server crash notifications."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            del channels[str(channel.id)]
        await ctx.reply(
            f"Channel {channel.mention} will no longer receive notifications about server crashes."
        )

    @scegroup.command()
    @checks.admin()
    async def checkchannels(self, ctx: commands.Context):
        """Check channels subscribed to server crash notifications."""
        channel_ids = await self.config.channels()
        if not channel_ids:
            await ctx.reply("No channels.")
        else:
            await ctx.reply(
                "\n".join(self.bot.get_channel(int(ch)).mention for ch in channel_ids)
            )
