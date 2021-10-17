import asyncio
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from copy import copy
import re
from typing import Optional
from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse

class RoundReminder(commands.Cog):
    default_user_settings = {'match_strings': []}
    GOON_COLOUR = discord.Colour.from_rgb(222, 190, 49)
    SUCCESS_REPLY = {'status': 'ok'}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=77984122151871643842)
        self.config.register_user(**self.default_user_settings)

    class SpacebeeError(Exception):
        def __init__(self, message: str, status_code: int, error_code: int = 0):
            self.message = message
            self.status_code = status_code
            self.error_code = error_code

    async def server_dep(self, server: str, server_name: str, api_key: str):
        if api_key != (await self.bot.get_shared_api_tokens('spacebee'))['api_key']:
            raise self.SpacebeeError("Invalid API key.", 403)
        goonservers = self.bot.get_cog('GoonServers')
        server = goonservers.resolve_server(server_name) or goonservers.resolve_server(server)
        if server is None:
            raise self.SpacebeeError("Unknown server.", 404)
        return server

    def register_to_general_api(self, app):
        @app.exception_handler(self.SpacebeeError)
        async def invalid_api_key_error_handler(request: Request, exc: self.SpacebeeError):
            return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "status": "error",
                        "errormsg": exc.message,
                        "error": exc.error_code,
                        },
                    )

        @app.get("/event")
        async def event(type: str, request: Request, server = Depends(self.server_dep)):
            goonservers = self.bot.get_cog("GoonServers")
            if type == 'serverstart':
                embed = discord.Embed()
                embed.title = server.full_name
                if server.url:
                    embed.url = server.url
                embed.description = "is starting a new round!"
                embed.add_field(name="Map", value=request.query_params['map'])
                embed.add_field(name="Gamemode", value=request.query_params['gamemode'])
                embed.colour = self.GOON_COLOUR
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/412381738510319626/892497840151076904/logo.png")
                for channel_id in server.subtype.channels['updates']:
                    await self.bot.get_channel(channel_id).send(embed=embed)
                await self.process_embed(embed)
                await goonservers.send_to_servers(server.subtype.servers, {
                        'type': "roundEnd",
                        'server': server.full_name,
                        'address': server.connect_url,
                    }, exception=server)
                return self.SUCCESS_REPLY
            elif type == 'login':
                self.bot.dispatch("goon_login",  server, str(list(request.query_params.keys())[1]))
                return self.SUCCESS_REPLY
            elif type == 'roundstart':
                return self.SUCCESS_REPLY
            elif type == 'roundend':
                return self.SUCCESS_REPLY
            elif type == 'shuttlecall':
                return self.SUCCESS_REPLY
            elif type == 'shuttledock':
                return self.SUCCESS_REPLY
            elif type == 'shuttlerecall':
                return self.SUCCESS_REPLY

    def normalize(self, text):
        if text is None:
            return text
        return ''.join(c for c in text.lower() if c.isalnum())

    @commands.command()
    async def nextround(self, ctx: commands.Context, *, search_text: Optional[str]):
        """Notifies you about the next round or the next round with server or map name containing `search_text`."""
        async with self.config.user(ctx.author).match_strings() as match_strings:
            match_strings.append(self.normalize(search_text))
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    async def notify(self, user: discord.User, embed, match_string: Optional[str]):
        try:
            text_message = "nextround reminder"
            if match_string is not None:
                text_message += f" for `{match_string}`"
            text_message += ":"
            await user.send(text_message, embed=embed)
        except discord.errors.Forbidden:
            # it's their fault if they don't open DMs!
            pass

    async def process_embed(self, embed):
        goonservers = self.bot.get_cog('GoonServers')
        server = goonservers.resolve_server(embed.title)
        fulltext = ' '.join(f.value for f in embed.fields)
        fulltext = self.normalize(fulltext)

        for user_id, data in (await self.config.all_users()).items():
            match_strings = data['match_strings']
            for match_string in match_strings:
                match = False
                if match_string is None:
                    match = True
                elif len(match_string) > 1 and match_string in fulltext:
                    match = True
                elif server in goonservers.resolve_server_or_category(match_string):
                    match = True
                if match:
                    user = self.bot.get_user(user_id)
                    await self.notify(user, embed, match_string)
                    if len(match_strings) == 1:
                        await self.config.user(user).match_strings.clear()
                    else:
                        match_strings.remove(match_string)
                        await self.config.user(user).match_strings.set(match_strings)
                    break

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        try:
            if message.channel.id != 421047584623427584: # TODO unhardcode #game-updates
                return
            if message.author == self.bot.user:
                return
            if len(message.embeds) > 0:
                embed = message.embeds[0]
                await process_embed(embed)
        except:
            import traceback
            return await self.bot.send_to_owners(traceback.format_exc())

