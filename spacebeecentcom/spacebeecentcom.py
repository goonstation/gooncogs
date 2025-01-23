import asyncio
import discord
import datetime
from redbot.core import commands, Config, checks, app_commands
from redbot.core.utils.chat_formatting import pagify
import discord.errors
from redbot.core.bot import Red
from typing import *
from fastapi import Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from github import Github
from collections import OrderedDict
import logging
import re
import secrets
import itertools
import discord.ui as ui

PLAYER_ROLE_ID = 182284445837950977
GUILD_ID = 182249960895545344

class SpacebeeCentcom(commands.Cog):
    AHELP_COLOUR = discord.Colour.from_rgb(184, 46, 0)
    ASAY_COLOUR = discord.Colour.from_rgb(174, 80, 186)
    MHELP_COLOUR = discord.Colour.from_rgb(123, 0, 255)
    SUCCESS_REPLY = {"status": "ok"}
    default_user_settings = {
        "linked_ckey": None,
        "link_verification": None,
    }
    MAX_CACHE_LENGTH = 2000
    REPLIED_TO_EMOJI = "\N{CLOSED MAILBOX WITH LOWERED FLAG}"

    def __init__(self, bot: Red):
        self.bot = bot
        self.asay_uses_embed = False
        self.config = Config.get_conf(self, identifier=5525879512398)
        self.config.init_custom("ckey", 1)
        self.config.register_user(**self.default_user_settings)
        self.config.register_custom("ckey", discord_id=None)
        self.gh = None
        self.id_to_messages = OrderedDict()
        self.message_to_id = OrderedDict()
        self.initiating_messages = OrderedDict()

    async def init(self):
        self.gh = Github((await self.bot.get_shared_api_tokens("github")).get("token"))

    class SpacebeeError(Exception):
        def __init__(self, message: str, status_code: int, error_code: int = 0):
            self.message = message
            self.status_code = status_code
            self.error_code = error_code

    def userid_mention(self, user_id):
        user = self.bot.get_user(user_id)
        if user:
            return user.mention
        else:
            return f"deleted-user ({user_id})"

    def make_message_embed(
        self,
        colour,
        from_key,
        from_name,
        message,
        embed_tag,
        server_name,
        to_key=None,
        to_name=None,
        url=None,
    ):
        embed = discord.Embed()
        embed.title = f"{from_key}/{from_name}"
        if to_key is not None:
            embed.title += f" \N{RIGHTWARDS ARROW} {to_key}/{to_name}"
        if url is not None:
            embed.url = url
        embed_tag = embed_tag
        embed.description = message
        embed.colour = colour
        embed.set_footer(text=f"{server_name} {embed_tag}")
        return embed

    async def is_initiating_message(self, message: discord.Message):
        if len(message.embeds) == 0:
            return False
        embed = message.embeds[0]
        if not isinstance(embed.footer.text, str):
            return False
        msg_type = embed.footer.text.split()[-1]
        return msg_type in ["MENTORHELP", "ADMINHELP"] 

    async def mark_initiating_message_reply(self, message: discord.Message):
        await message.add_reaction(self.REPLIED_TO_EMOJI)
        if message.id in self.initiating_messages:
            del self.initiating_messages[message.id]

    async def discord_broadcast(self,
            channels,
            *args,
            exception=None,
            reply_message_list=None,
            reply_message_id=None,
            msgid=None,
            **kwargs
        ):
        channel_to_reply_message = {}
        if reply_message_id is not None and reply_message_id in self.id_to_messages:
            reply_message_list = self.id_to_messages[reply_message_id]
        if reply_message_list is not None:
            for message in reply_message_list:
                channel_to_reply_message[message.channel.id] = message
        async def task(ch):
            reply_message = channel_to_reply_message.get(ch, None)
            result_msg = await self.bot.get_channel(ch).send(*args, **kwargs, reference=reply_message)
            if reply_message and await self.is_initiating_message(reply_message):
                await self.mark_initiating_message_reply(reply_message)
            return result_msg
        tasks = [
            task(ch)
            for ch in channels
            if ch != exception
        ]
        messages = await asyncio.gather(*tasks)
        if msgid:
            self.id_to_messages[msgid] = list(messages)
            for message in messages:
                self.message_to_id[message] = msgid
                if await self.is_initiating_message(message):
                    self.initiating_messages[message.id] = message
            if len(self.id_to_messages) > self.MAX_CACHE_LENGTH:
                new_size = self.MAX_CACHE_LENGTH // 2
                for _ in range(new_size):
                    self.id_to_messages.popitem(last=False)
                new_message_to_id_size = len(self.message_to_id) // 2
                for _ in range(new_message_to_id_size):
                    self.message_to_id.popitem(last=False)
            if len(self.initiating_messages) > self.MAX_CACHE_LENGTH:
                new_size = self.MAX_CACHE_LENGTH // 2
                for _ in range(new_size):
                    self.initiating_messages.popitem(last=False)
        return messages

    async def discord_broadcast_ahelp(
        self,
        channels,
        server_name,
        from_key,
        from_name,
        msg,
        to_key=None,
        to_name=None,
        exception=None,
        url=None,
        msgid=None,
        reply_message_id=None,
    ):
        embed_tag = "ADMINPM" if to_key is not None else "ADMINHELP"
        embed = self.make_message_embed(
            self.AHELP_COLOUR,
            from_key,
            from_name,
            msg,
            embed_tag,
            server_name,
            to_key,
            to_name,
            url,
        )
        if hasattr(channels, "channels"):
            channels = channels.channels["ahelp"]
        await self.discord_broadcast(channels, embed=embed, exception=exception, msgid=msgid, reply_message_id=reply_message_id)

    async def discord_broadcast_mhelp(
        self,
        channels,
        server_name,
        from_key,
        from_name,
        msg,
        to_key=None,
        to_name=None,
        exception=None,
        msgid=None,
        reply_message_id=None,
    ):
        embed_tag = "MENTORPM" if to_key is not None else "MENTORHELP"
        embed = self.make_message_embed(
            self.MHELP_COLOUR,
            from_key,
            from_name,
            msg,
            embed_tag,
            server_name,
            to_key,
            to_name,
        )
        if hasattr(channels, "channels"):
            channels = channels.channels["mhelp"]
        await self.discord_broadcast(channels, embed=embed, exception=exception, msgid=msgid, reply_message_id=reply_message_id)

    async def discord_broadcast_uncool(
            self, channels, server_name, key, name, message, phrase, word, server_key, exception=None, msgid=None, reply_message_id=None
    ):
        embed = self.make_message_embed(
            discord.Colour.from_rgb(255, 255, 0),
            key,
            name,
            f"{message}: {phrase}",
            "UNCOOL",
            server_name
        )
        view = UncoolHandlerView(self.bot, key, word, phrase, server_key)
        if hasattr(channels, "channels"):
            channels = channels.channels["ahelp"]
        view.messages = await self.discord_broadcast(channels, embed=embed, exception=exception, msgid=msgid, reply_message_id=reply_message_id, view = view)

    async def discord_broadcast_asay(
        self, channels, server_name, from_key, from_name, source, msg, exception=None
    ):
        if hasattr(channels, "channels"):
            channels = channels.channels["asay"]
        if self.asay_uses_embed:
            embed = self.make_message_embed(
                self.ASAY_COLOUR, from_key, from_name, msg, "ASAY", server_name
            )
            await self.discord_broadcast(channels, embed=embed, exception=exception)
        else:
            out_msg = f"\N{LARGE PURPLE SQUARE} [{source}] __{from_key}__: {msg}"
            await self.discord_broadcast(channels, out_msg, exception=exception)

    async def game_broadcast_asay(
        self, servers, from_key, from_name, source, msg, exception=None
    ):
        goonservers = self.bot.get_cog("GoonServers")
        send_data = {
            "type": "asay",
            "nick": f"[{source}] {from_key}" if source is not None else from_key,
            "msg": msg,
        }
        await goonservers.send_to_servers(servers, send_data, exception=exception)

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

        @app.get("/asay")
        async def adminsay(
            key: str, name: str, msg: str, server=Depends(self.server_dep)
        ):
            await self.discord_broadcast_asay(
                server.subtype, server.full_name, key, name, server.short_name, msg
            )
            await self.game_broadcast_asay(
                server.subtype.servers,
                key,
                name,
                server.short_name,
                msg,
                exception=server,
            )
            return self.SUCCESS_REPLY

        @app.get("/uncool")
        async def adminsay(
            key: str, name: str, msg: str, phrase: str, pos: int, server_key: str, server=Depends(self.server_dep)
        ):
            words = phrase.split('**')
            char_positions = list(itertools.accumulate(len(word) + 2 for word in words))
            word = None
            for i, pos2 in enumerate(char_positions):
                if pos < pos2:
                    word = words[i]
                    break

            await self.discord_broadcast_uncool(
                server.subtype, server.full_name, key, name, msg, phrase, word, server_key
            )
            return self.SUCCESS_REPLY

        @app.get("/ban")
        async def ban(
            key: str,
            key2: str,
            msg: str,
            time: str,
            timestamp: Optional[float],
            server=Depends(self.server_dep),
        ):
            embed = discord.Embed()
            embed.title = f"{key} banned {key2}"
            embed.description = msg
            if timestamp is None:
                embed.add_field(name="expires", value=f"in {time}")
            if timestamp > 0:
                timestamp = (
                    int(timestamp) * 60 + 946684800
                )  # timestamp is send in minutes since 2000-01-01 00:00 GMT
                embed.add_field(
                    name="expires", value=f"<t:{timestamp}:F>\n(<t:{timestamp}:R>)"
                )
            elif timestamp == 0:
                embed.add_field(name="expires", value="permanent")
            else:
                embed.add_field(name="expires", value="until appeal")
            embed.colour = discord.Colour.red()
            embed.set_footer(text=f"{server.full_name} BAN")
            for channel_id in server.subtype.channels["ban"]:
                await self.bot.get_channel(channel_id).send(embed=embed)
            return self.SUCCESS_REPLY

        @app.get("/job_ban")
        async def job_ban(
            key: str,
            rank: str,
            akey: str,
            applicable_server: str,
            server=Depends(self.server_dep),
        ):
            embed = discord.Embed()
            embed.title = f"{akey} jobbanned {key} from {rank}"
            applicable_server = applicable_server or "all"
            embed.description = f"server `{applicable_server}`"
            embed.colour = discord.Colour.from_rgb(200, 100, 100)
            embed.set_footer(text=f"{server.full_name} JOBBAN")
            for channel_id in server.subtype.channels["ban"]:
                await self.bot.get_channel(channel_id).send(embed=embed)
            return self.SUCCESS_REPLY

        @app.get("/job_unban")
        async def job_unban(
            key: str,
            rank: str,
            akey: str,
            applicable_server: str,
            server=Depends(self.server_dep),
        ):
            embed = discord.Embed()
            embed.title = f"{akey} jobUNbanned {key} from {rank}"
            applicable_server = applicable_server or "all"
            embed.description = f"server `{applicable_server}`"
            embed.colour = discord.Colour.from_rgb(200, 100, 100)
            embed.set_footer(text=f"{server.full_name} JOBUNBAN")
            for channel_id in server.subtype.channels["ban"]:
                await self.bot.get_channel(channel_id).send(embed=embed)
            return self.SUCCESS_REPLY

        @app.get("/help")
        async def adminhelp(
            key: str,
            name: str,
            msg: str,
            log_link: Optional[str] = None,
            msgid: Optional[str] = None,
            previous_msgid: Optional[str] = None,
            server=Depends(self.server_dep),
        ):
            await self.discord_broadcast_ahelp(
                server.subtype, server.full_name, key, name, msg, url=log_link, msgid=msgid, reply_message_id=previous_msgid
            )
            return self.SUCCESS_REPLY

        @app.get("/pm")
        async def adminpm(
            key: str,
            name: str,
            key2: str,
            name2: str,
            msg: str,
            msgid: Optional[str] = None,
            previous_msgid: Optional[str] = None,
            server=Depends(self.server_dep),
        ):
            await self.discord_broadcast_ahelp(
                server.subtype, server.full_name, key, name, msg, key2, name2, msgid=msgid, reply_message_id=previous_msgid
            )
            return self.SUCCESS_REPLY

        @app.get("/mentorhelp")
        async def mentorhelp(
            key: str,
            name: str,
            msg: str,
            msgid: Optional[str] = None,
            previous_msgid: Optional[str] = None,
            server=Depends(self.server_dep)
        ):
            await self.discord_broadcast_mhelp(
                server.subtype, server.full_name, key, name, msg, msgid=msgid, reply_message_id=previous_msgid
            )
            return self.SUCCESS_REPLY

        @app.get("/mentorpm")
        async def mentorpm(
            key: str,
            name: str,
            key2: str,
            name2: str,
            msg: str,
            msgid: Optional[str] = None,
            previous_msgid: Optional[str] = None,
            server=Depends(self.server_dep),
        ):
            await self.discord_broadcast_mhelp(
                server.subtype, server.full_name, key, name, msg, key2, name2, msgid=msgid, reply_message_id=previous_msgid
            )
            return self.SUCCESS_REPLY

        @app.get("/admin")
        async def admin(
            msg: str, key: str = "", name: str = "", server=Depends(self.server_dep)
        ):
            out = f"[{server.full_name}] "
            if key or name:
                out += f"{name} ({key}) "
            out += msg
            await server.subtype.channel_broadcast(self.bot, "admin_misc", out)
            return self.SUCCESS_REPLY

        @app.get("/admin_debug")
        async def admin_debug(
            msg: str, key: str = "", name: str = "", server=Depends(self.server_dep)
        ):
            out = f"[{server.full_name}] "
            if key or name:
                out += f"{name} ({key}) "
            out += msg
            await server.subtype.channel_broadcast(self.bot, "debug", out)
            return self.SUCCESS_REPLY

        @app.get("/issue")
        async def admin_debug(
            title: str, body: str, secret: bool, server=Depends(self.server_dep)
        ):
            repo_name = (
                "goonstation/goonstation-secret"
                if secret
                else "goonstation/goonstation"
            )
            repo = self.gh.get_repo(repo_name)
            repo.create_issue(title, body)
            return self.SUCCESS_REPLY

        @app.get("/link")
        async def link(key: str, ckey: str, code: str, server=Depends(self.server_dep)):
            if "-" not in code:
                return {"status": "error", "response": "Invalid format of the link code", "errormsg": f"Invalid link code format '{code}'"}
            code = code.strip()
            user_id, verification = code.split("-")
            user_id = int(user_id)
            user = self.bot.get_user(user_id)
            if user is None:
                return {"status": "error", "response": "Invalid user id part of the link code", "errormsg": f"Invalid link code user ID format '{code}'"}
            target_verif = await self.config.user(user).link_verification()
            if target_verif != verification:
                return {"status": "error", "response": "Wrong link verification code", "errormsg": f"Invalid link code verification '{code}'"}
            ckeys_linked_account = await self.config.custom("ckey", ckey).discord_id()
            if ckeys_linked_account:
                try:
                    await user.send(
                        f"Ckey `{ckey}` is already linked to {'your' if user_id == ckeys_linked_account else 'another'} account."
                    )
                except:
                    pass
                return {"status": "error", "response": "Your byond account is already linked to an account", "errormsg": f"User already linked"}
            await self.config.user(user).link_verification.set(None)
            await self.config.user(user).linked_ckey.set(ckey)
            await self.config.custom("ckey", ckey).discord_id.set(user_id)
            try:
                await user.send(f"Account successfully linked to ckey `{ckey}`.")
            except:
                pass
            guild = self.bot.get_guild(GUILD_ID)
            member = await guild.fetch_member(user_id)
            if member is not None:
                await member.add_roles(guild.get_role(PLAYER_ROLE_ID))
                logging.info(f"Successfully added player role to {member.mention}")
            else:
                logging.info(f"Failed to add player role to {member.mention}")
            return self.SUCCESS_REPLY

    def ckeyify(self, text):
        return "".join(c.lower() for c in text if c.isalnum())

    async def get_ckey(self, member: discord.Member):
        return await self.config.user(member).linked_ckey()

    @commands.command()
    async def link(self, ctx: commands.Context):
        """Links your Discord account with your BYOND username and gives you the Player role."""
        current_ckey = await self.config.user(ctx.author).linked_ckey()
        if current_ckey:
            await ctx.send(
                f"You are already linked to username `{current_ckey}`. If you wish to unlink please contact an administrator (ideally using the /report command)."
            )
            return
        verif = secrets.token_hex(8)
        full_verif = f"{ctx.author.id}-{verif}"
        await self.config.user(ctx.author).link_verification.set(verif)
        try:
            msg = f"Login into one of Goonstation servers and use the Link Discord verb in the Commands tab on the right. Enter code `{full_verif}` when prompted."
            await ctx.author.send(msg)
        except:
            await ctx.send("Either use the /link command or enable your DMs first.")

    @app_commands.command(name="link")
    async def slash_link(self, interaction: discord.Interaction):
        """Links your Discord account with your BYOND username and gives you the Player role."""
        current_ckey = await self.config.user(interaction.user).linked_ckey()
        if current_ckey:
            await interaction.response.send_message(
                f"You are already linked to username `{current_ckey}`. If you wish to unlink please contact an administrator (ideally using the /report command).",
                ephemeral=True
            )
            return
        verif = secrets.token_hex(8)
        full_verif = f"{interaction.user.id}-{verif}"
        await self.config.user(interaction.user).link_verification.set(verif)
        msg = f"Login into one of Goonstation servers and use the Link Discord verb in the Commands tab on the right. Enter code `{full_verif}` when prompted."
        await interaction.response.send_message(msg, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return
        current_ckey = await self.config.user(member).linked_ckey()
        if current_ckey:
            rolestuff_cog = self.bot.get_cog("RoleStuff")
            player_added = False
            if rolestuff_cog:
                roles_added, _ = await rolestuff_cog.restore_roles_internal(member)
                if any(r.id == PLAYER_ROLE_ID for r in roles_added):
                    player_added = True
            if not player_added:
                await member.add_roles(member.guild.get_role(PLAYER_ROLE_ID))

    @commands.command()
    @checks.admin()
    async def unlinkother(self, ctx: commands.Context, target: discord.User):
        """Unlinks a Discord user from their ckey."""
        current_ckey = await self.config.user(target).linked_ckey()
        if current_ckey:
            await self.config.user(target).linked_ckey.set(None)
            await self.config.custom("ckey", current_ckey).discord_id.set(None)
            await ctx.send(f"Unlinked ckey `{current_ckey}` from {target.mention}")
            guild = self.bot.get_guild(GUILD_ID)
            member = guild.get_member(target.id)
            if member:
                await member.remove_roles(guild.get_role(PLAYER_ROLE_ID))
        else:
            await ctx.send("They have no linked ckey")

    @commands.command()
    @checks.admin()
    async def unlinkotherckey(self, ctx: commands.Context, ckey: str):
        """Unlinks a ckey from their Discord account."""
        ckey = self.ckeyify(ckey)
        user_id = await self.config.custom("ckey", ckey).discord_id()
        if user_id:
            await self.config.user_from_id(user_id).linked_ckey.set(None)
            await self.config.custom("ckey", ckey).discord_id.set(None)
            await ctx.send(f"Unlinked ckey `{ckey}` from {self.userid_mention(user_id)}")
        else:
            await ctx.send("They have no linked Discord account")

    @commands.command()
    @checks.admin()
    async def linkother(
        self, ctx: commands.Context, target: discord.User, *, ckey: str
    ):
        """Directly links a Discord user to a BYOND ckey."""
        ckey = self.ckeyify(ckey)
        current_ckey = await self.config.user(target).linked_ckey()
        if current_ckey:
            await ctx.send(
                f"That user is already linked to a ckey `{current_ckey}`. Unlink it first."
            )
            return
        ckeys_linked_account = await self.config.custom("ckey", ckey).discord_id()
        if ckeys_linked_account:
            await ctx.send(
                f"That ckey is already linked to user <@{ckeys_linked_account}>."
            )
            return
        await self.config.user(target).linked_ckey.set(ckey)
        await self.config.custom("ckey", ckey).discord_id.set(target.id)
        msg = f"Linked ckey `{ckey}` to {target.mention}"
        if current_ckey:
            msg += f" (Their previous ckey was `{current_ckey}`)"
        guild = self.bot.get_guild(GUILD_ID)
        member = guild.get_member(target.id)
        if member:
            await member.add_roles(guild.get_role(PLAYER_ROLE_ID))
        await ctx.send(msg)

    async def user_to_ckey(self, user):
        return await self.config.user(user).linked_ckey()
    
    async def ckey_to_discord(self, ckey):
        return await self.config.custom("ckey", ckey).discord_id()

    @commands.command()
    @checks.admin()
    async def checklink(self, ctx: commands.Context, target: Union[discord.User, str]):
        """Checks linked account of a Discord user."""
        if not isinstance(target, str):
            current_ckey = await self.config.user(target).linked_ckey()
            if current_ckey:
                await ctx.send(f"{target.mention}'s ckey is `{current_ckey}`")
            else:
                await ctx.send(f"{target.mention} has not linked their account")
        else:
            ckey = self.ckeyify(target)
            user_id = await self.config.custom("ckey", ckey).discord_id()
            if user_id:
                await ctx.send(
                    f"`{ckey}`'s Discord account is {self.userid_mention(user_id)}"
                )
            else:
                await ctx.send(f"Ckey `{ckey}` has not lonked their Discord account")

    def get_server(self, server_id):
        goonservers_cog = self.bot.get_cog("GoonServers")
        return goonservers_cog.resolve_server(server_id)

    async def check_and_send_message(
            self, type, message: discord.Message, server_id, data, replied_to_msg: Optional[discord.Message] = None
    ):
        goonservers = self.bot.get_cog("GoonServers")
        server = goonservers.resolve_server(server_id)
        if not server:
            await message.reply("Unknown server.")
            return False
        if message.channel.id not in server.subtype.channels[type]:
            await message.reply("Wrong channel.")
            return False
        msgid = "Discord " + str(message.id)
        if type in ["ahelp", "mhelp"]:
            data["msgid"] = msgid
        previous_msgid = self.message_to_id.get(replied_to_msg, None)
        response = await goonservers.send_to_server_safe(
            server, data, message, to_dict=True
        )
        if response == 0.0:
            await message.reply("Could not find that person.")
            return False
        elif isinstance(response, dict):
            await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            if type == "ahelp":
                await self.discord_broadcast_ahelp(
                    server.subtype,
                    server.full_name,
                    response["key"],
                    "Discord",
                    response["msg"],
                    response["key2"],
                    response["name2"],
                    exception=message.channel.id,
                    msgid=msgid,
                    reply_message_id=previous_msgid,
                )
            elif type == "mhelp":
                await self.discord_broadcast_mhelp(
                    server.subtype,
                    server.full_name,
                    response["key"],
                    "Discord",
                    response["msg"],
                    response["key2"],
                    response["name2"],
                    exception=message.channel.id,
                    msgid=msgid,
                    reply_message_id=previous_msgid,
                )
            elif type == "asay":
                await self.discord_broadcast_asay(
                    server.subtype,
                    server.full_name,
                    response["key"],
                    "Discord",
                    "Discord",
                    response["msg"],
                    exception=message.channel.id,
                )
            if type in ["ahelp", "mhelp"]:
                self.message_to_id[message] = msgid
                self.id_to_messages[msgid].append(message)
            return True
        return False

    @commands.command()
    async def pm(
        self, ctx: commands.Context, server_id: str, target: str, *, message: str
    ):
        """Sends an admin PM to a given Goonstation server to a given ckey.

        You can also do this by using Discord replies on incoming adminhelps."""
        author_ckey = await self.get_ckey(ctx.author)
        if author_ckey is None:
            await ctx.reply("Your account needs to be linked to use this")
            return
        await self.check_and_send_message(
            "ahelp",
            ctx.message,
            server_id,
            {
                "type": "pm",
                "nick": author_ckey,
                "msg": message,
                "target": target,
            },
        )

    @commands.command()
    async def asay(self, ctx: commands.Context, server_id: str, *, message: str):
        """Sends an adminsay message to a given Goonstation server.

        You can also do this by using Discord replies on incoming asays."""
        author_ckey = await self.get_ckey(ctx.author)
        if author_ckey is None:
            await ctx.reply("Your account needs to be linked to use this")
            return
        await self.check_and_send_message(
            "asay",
            ctx.message,
            server_id,
            {
                "type": "asay",
                "nick": author_ckey,
                "msg": message,
            },
        )

    @commands.command(aliases=["mpm"])
    async def mentorpm(
        self, ctx: commands.Context, server_id: str, target: str, *, message: str
    ):
        """Sends a mentor PM to a given Goonstation server to a given ckey.

        You can also do this by using Discord replies on incoming mentorhelps."""
        author_ckey = await self.get_ckey(ctx.author)
        if author_ckey is None:
            await ctx.reply("Your account needs to be linked to use this")
            return
        await self.check_and_send_message(
            "mhelp",
            ctx.message,
            server_id,
            {
                "type": "mentorpm",
                "nick": author_ckey,
                "msg": message,
                "target": target,
            },
        )

    async def process_semicolon_asay(self, message: discord.Message):
        goonservers = self.bot.get_cog("GoonServers")
        if message.clean_content[0] != ";":
            return False
        author_ckey = await self.get_ckey(message.author)
        if author_ckey is None:
            await message.reply("Your account needs to be linked to use this")
            return
        msg = message.clean_content[1:].strip()
        asay_servers = goonservers.channel_to_servers(message.channel.id, "asay")
        target_channels = set()
        for server in asay_servers:
            target_channels |= set(server.subtype.channels["asay"])

        data = {"type": "asay", "nick": author_ckey, "msg": msg}

        await goonservers.send_to_servers(asay_servers, data)
        await self.discord_broadcast_asay(
            target_channels,
            "Discord",
            author_ckey,
            message.author.name,
            "Discord",
            msg,
            exception=message.channel.id,
        )
        return True

    @commands.command()
    async def unanswered(self, ctx: commands.Context):
        """
        Lists unanswered messages in this channel in reverse chronological order.

        You can react with \N{CLOSED MAILBOX WITH LOWERED FLAG} manually to a message to mark
        it as resolved. Only messages from last 24 hours or since last bot restart are displayed.
        """
        author_ckey = await self.get_ckey(ctx.author)
        if author_ckey is None:
            await ctx.reply("Your account needs to be linked to use this")
            return
        goonservers = self.bot.get_cog("GoonServers")
        if ctx.channel.id not in goonservers.valid_channels:
            await ctx.reply("Wrong channel.")
            return False
        unanswered_list = []
        for msg in reversed(self.initiating_messages.values()):
            if (datetime.datetime.now().replace(tzinfo=None) - msg.created_at.replace(tzinfo=None)) > datetime.timedelta(days = 1):
                break
            if await self.is_initiating_message(msg) and \
                    not any(react.emoji == self.REPLIED_TO_EMOJI for react in msg.reactions) and \
                    msg.channel == ctx.channel:
                unanswered_list.append(msg)
        def format_msg(msg):
            msg_text = ""
            if len(msg.embeds) > 0 and msg.embeds[0].description:
                msg_text = msg.embeds[0].description
                if len(msg_text) > 100:
                    msg_text = msg_text[:97] + "..."
            return msg.jump_url + " " + msg_text
        if len(unanswered_list) == 0:
            await ctx.reply("No unanswered messages!")
        else:
            for page in pagify("\n".join(format_msg(msg) for msg in unanswered_list)):
                await ctx.reply(page)

    async def process_discord_replies(self, message: discord.Message):
        reference = message.reference
        if reference is None:
            return
        replied_to_msg = reference.resolved
        if not isinstance(replied_to_msg, discord.Message):
            return
        if replied_to_msg.author.id != self.bot.user.id:
            return
        target = None
        server_id = None
        reply_type = None
        channel_type = None
        if len(replied_to_msg.embeds) > 0:
            embed = replied_to_msg.embeds[0]
            target = embed.title.split("/")[0]
            if not isinstance(embed.footer.text, str):
                return
            msg_type = embed.footer.text.split()[-1]
            server_id = embed.footer.text[: -len(msg_type) - 1]
            reply_type = None
            if msg_type in ["ADMINHELP", "ADMINPM"]:
                reply_type = "pm"
                channel_type = "ahelp"
            elif msg_type in ["MENTORHELP", "MENTORPM"]:
                reply_type = "mentorpm"
                channel_type = "mhelp"
            elif msg_type == "ASAY":
                reply_type = "asay"
                channel_type = "asay"
            else:
                return
        elif replied_to_msg.content[0] == "\N{LARGE PURPLE SQUARE}":
            match = re.match(
                "\N{LARGE PURPLE SQUARE} " + r"\[(.*?)\] ([^:]*): .*",
                replied_to_msg.content,
            )
            if match:
                server_id, target = match.groups()
                reply_type = "asay"
                channel_type = "asay"

        if reply_type is None:
            return

        author_ckey = await self.get_ckey(message.author)
        if author_ckey is None:
            await message.reply("Your account needs to be linked to use this")
            return

        if await self.is_initiating_message(replied_to_msg):
            await self.mark_initiating_message_reply(replied_to_msg)

        await self.check_and_send_message(
            channel_type,
            message,
            server_id,
            {
                "type": reply_type,
                "nick": author_ckey,
                "msg": message.content,
                "target": target,
            },
            replied_to_msg=replied_to_msg,
        )

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        goonservers = self.bot.get_cog("GoonServers")
        if not goonservers:
            return
        if message.channel.id not in goonservers.valid_channels:
            return
        if message.guild is None or self.bot.user == message.author:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        valid_user = (
            isinstance(message.author, discord.Member) and not message.author.bot
        )
        if not valid_user:
            return
        if not message.clean_content:
            return

        try:
            if not await self.process_semicolon_asay(message):
                await self.process_discord_replies(message)
        except:
            import traceback

            await self.bot.send_to_owners(traceback.format_exc())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) == self.REPLIED_TO_EMOJI and payload.message_id in self.initiating_messages:
            del self.initiating_messages[payload.message_id]

class UncoolHandlerView(ui.View):
    def __init__(self, bot, key, word, phrase, server_key):
        super().__init__(timeout = 1800)
        self.bot = bot
        self.key = key
        self.word = word
        self.phrase = phrase
        self.server_key = server_key
        self.messages = None

    @ui.button(label="Ban", style=discord.ButtonStyle.red)
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UncoolBanModal(self.bot, self.key, self.word, self.phrase, self.server_key))
    @ui.button(label="Warn", style=discord.ButtonStyle.blurple)
    async def warn_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UncoolWarnModal(self.bot, self.key, self.word, self.phrase, self.server_key))

    @ui.button(label="Notes", style=discord.ButtonStyle.green)
    async def notes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        goonservers = self.bot.get_cog("GoonServers")
        spacebeecentcom = self.bot.get_cog("SpacebeeCentcom")
        name = await spacebeecentcom.get_ckey(interaction.user)

        if name is None:
            await interaction.response.send_message("Your account needs to be linked to use this button", ephemeral=True)
            return

        msg = f"notes{self.server_key} {self.key}"
        await goonservers.send_to_server(goonservers.resolve_server(self.server_key), f"type=asay&nick={name}&msg=%3B{msg}")
        await interaction.response.defer(ephemeral=True)

    @ui.button(label="Dismiss", style=discord.ButtonStyle.grey)
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        for message in self.messages:
            embed: discord.Embed = message.embeds[0]
            embed.title = f"~~{embed.title}~~ (DISMISSED)"
            await message.edit(view=None, embed = embed)

    async def on_timeout(self):
        await super().on_timeout()
        for message in self.messages:
            await message.edit(view=None)

class UncoolBanModal(ui.Modal):
    def __init__(self, bot, key, word, phrase, server_key):
        super().__init__(title = f"Banning {key[:30]}")
        self.bot = bot
        self.key = key
        self.server_key = server_key
        self.duration = ui.TextInput(label = "ban duration in minutes", default = "60")
        self.reason = ui.TextInput(label = "Reason given for ban", default = f"Per rule 4, do not say {word} on our servers")

        self.add_item(ui.TextInput(label = f"{word[:70]}", default = f"{phrase[:4000]}", style=discord.TextStyle.long))
        self.add_item(self.duration)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        goonservers = self.bot.get_cog("GoonServers")
        spacebeecentcom = self.bot.get_cog("SpacebeeCentcom")

        name = await spacebeecentcom.get_ckey(interaction.user)

        if name is None:
            await interaction.response.send_message("Your account needs to be linked to use this button", ephemeral=True)
            return

        msg = f"ban{self.server_key} {self.key} {self.duration.value} {self.reason.value}"
        await goonservers.send_to_server(goonservers.resolve_server(self.server_key), f"type=asay&nick={name}&msg=%3B{msg}")
        await interaction.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await interaction.response.defer(ephemeral=True)

class UncoolWarnModal(ui.Modal):
    def __init__(self, bot, key, word: str, phrase, server_key):
        super().__init__(title = f"Warning {key[:30]}")
        self.bot = bot
        self.key = key
        self.server_key = server_key

        if "brutality" in word.lower():
            self.warn = ui.TextInput(label = "Warn message", default = f"Please don't refer to '{word}' on Goonstation. Players who roll Sec are not police officers and we want to keep a firm line between the game and real world issues.")
        else:
            self.warn = ui.TextInput(label = "Warn message", default = f"Per rule 4, do not say \'{word}\' on our servers")
        self.note = ui.TextInput(label = "Note message", default = f"Warned for {word}\n{phrase[:250]}", style=discord.TextStyle.long)

        self.add_item(ui.TextInput(label = f"{word[:70]}", default = f"{phrase[:4000]}", style=discord.TextStyle.long))
        self.add_item(self.warn)
        self.add_item(self.note)


    async def on_submit(self, interaction: discord.Interaction):
        goonservers = self.bot.get_cog("GoonServers")
        spacebeecentcom: SpacebeeCentcom = self.bot.get_cog("SpacebeeCentcom")

        name = await spacebeecentcom.get_ckey(interaction.user)

        if name is None:
            await interaction.response.send_message("Your account needs to be linked to use this button", ephemeral=True)
            return

        msg = f"addnote{self.server_key} {self.key} {self.note.value}"
        await goonservers.send_to_server(goonservers.resolve_server(self.server_key), f"type=asay&nick={name}&msg=%3B{msg}")
        #SEND ADMIN PM
        await interaction.response.send_message(f"{self.warn.value}")
        await spacebeecentcom.check_and_send_message(
            "ahelp",
            await interaction.original_response(),
            self.server_key,
            {
                "type": "pm",
                "nick": name,
                "msg": f"{self.warn.value}",
                "target": self.key,
            },
        )
        await interaction.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

@app_commands.context_menu(name="Check Link")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.default_permissions()
async def check_link(interaction: discord.Interaction, target: discord.Member):
    cog = interaction.client.get_cog("SpacebeeCentcom")
    if not isinstance(cog, SpacebeeCentcom):
        await interaction.response.send_message("Something went horribly wrong oh no!", ephemeral=True)
        return

    current_ckey = await cog.config.user(target).linked_ckey()
    if not current_ckey:
        await interaction.response.send_message(f"{target.mention} has not linked their account", ephemeral=True)
    else:
        await interaction.response.send_message(f"{target.mention}'s ckey is [`{current_ckey}`](<https://goonhub.com/admin/players/{current_ckey}>)", ephemeral=True, suppress_embeds=True)
