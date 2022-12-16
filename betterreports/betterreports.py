import logging
import asyncio
from typing import Union, List, Literal, Optional
from datetime import timedelta
from copy import copy
import contextlib
import discord
import gc

from redbot.core import Config, checks, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.antispam import AntiSpam
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n, set_contextual_locales_from_guild
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.tunnel import Tunnel

from discord_slash import SlashCommand, SlashContext
from discord_slash.cog_ext import cog_slash


_ = Translator("Reports", __file__)

log = logging.getLogger("red.goon.reports")


@cog_i18n(_)
class BetterReports(commands.Cog):
    """Create user reports that server staff can respond to.

    Users can open reports using `[p]report`. These are then sent
    to a channel in the server for staff, and the report creator
    gets a DM. Both can be used to communicate.
    """

    default_guild_settings = {"output_channel": None, "active": False, "next_ticket": 1}

    default_report = {"report": {}}

    # This can be made configureable later if it
    # becomes an issue.
    # Intervals should be a list of tuples in the form
    # (period: timedelta, max_frequency: int)
    # see redbot/core/utils/antispam.py for more details

    intervals = [
        (timedelta(seconds=5), 1),
        (timedelta(minutes=5), 3),
        (timedelta(hours=1), 10),
        (timedelta(days=1), 24),
    ]

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 78631113035100160, force_registration=True)
        self.config.register_guild(**self.default_guild_settings)
        self.config.init_custom("REPORT", 2)
        self.config.register_custom("REPORT", **self.default_report)
        self.antispam = {}
        self.user_cache = []
        self.tunnel_store = {}
        # (guild, ticket#):
        #   {'tun': Tunnel, 'msgs': List[int]}
        self.bot.slash.get_cog_commands(self)

    @property
    def default_guild(self):
        return self.bot.get_guild(182249960895545344)

    def cog_unload(self):
        self.bot.slash.remove_cog_commands(self)

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        if requester != "discord_deleted_user":
            return

        all_reports = await self.config.custom("REPORT").all()

        steps = 0
        paths = []

        # this doesn't use async iter intentionally due to the nested iterations
        for guild_id_str, tickets in all_reports.items():
            for ticket_number, ticket in tickets.items():
                steps += 1
                if not steps % 100:
                    await asyncio.sleep(0)  # yield context

            if ticket.get("report", {}).get("user_id", 0) == user_id:
                paths.append((guild_id_str, ticket_number))

        async with self.config.custom("REPORT").all() as all_reports:
            async for guild_id_str, ticket_number in AsyncIter(paths, steps=100):
                r = all_reports[guild_id_str][ticket_number]["report"]
                r["user_id"] = 0xDE1
                # this might include EUD, and a report of a deleted user
                # that's been unhandled for long enough for the
                # user to be deleted and the bot receive a request like this...
                r["report"] = "[REPORT DELETED DUE TO DISCORD REQUEST]"

    @property
    def tunnels(self):
        return [x["tun"] for x in self.tunnel_store.values()]

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="reportset")
    async def reportset(self, ctx: commands.Context):
        """Manage Reports."""
        pass

    @checks.admin_or_permissions(manage_guild=True)
    @reportset.command(name="output")
    async def reportset_output(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Set the channel where reports will be sent."""
        await self.config.guild(ctx.guild).output_channel.set(channel.id)
        await ctx.send(_("The report channel has been set."))

    @checks.admin_or_permissions(manage_guild=True)
    @reportset.command(name="toggle", aliases=["toggleactive"])
    async def reportset_toggle(self, ctx: commands.Context):
        """Enable or Disable reporting for this server."""
        active = await self.config.guild(ctx.guild).active()
        active = not active
        await self.config.guild(ctx.guild).active.set(active)
        if active:
            await ctx.send(_("Reporting is now enabled"))
        else:
            await ctx.send(_("Reporting is now disabled."))

    async def internal_filter(self, m: discord.Member, mod=False, perms=None):
        if perms and m.guild_permissions >= perms:
            return True
        if mod and await self.bot.is_mod(m):
            return True
        # The following line is for consistency with how perms are handled
        # in Red, though I'm not sure it makes sense to use here.
        if await self.bot.is_owner(m):
            return True

    async def discover_guild(
        self,
        author: discord.User,
        *,
        mod: bool = False,
        permissions: Union[discord.Permissions, dict] = None,
        prompt: str = "",
    ):
        """
        discovers which of shared guilds between the bot
        and provided user based on conditions (mod or permissions is an or)

        prompt is for providing a user prompt for selection
        """
        shared_guilds = []
        if permissions is None:
            perms = discord.Permissions()
        elif isinstance(permissions, discord.Permissions):
            perms = permissions
        else:
            perms = discord.Permissions(**permissions)

        async for guild in AsyncIter(self.bot.guilds, steps=100):
            x = guild.get_member(author.id)
            if x is not None:
                if await self.internal_filter(x, mod, perms):
                    shared_guilds.append(guild)
        if len(shared_guilds) == 0:
            raise ValueError("No Qualifying Shared Guilds")
        if len(shared_guilds) == 1:
            return shared_guilds[0]
        output = ""
        guilds = sorted(shared_guilds, key=lambda g: g.name)
        for i, guild in enumerate(guilds, 1):
            output += "{}: {}\n".format(i, guild.name)
        output += "\n{}".format(prompt)

        for page in pagify(output, delims=["\n"]):
            await author.send(box(page))

        try:
            message = await self.bot.wait_for(
                "message",
                check=MessagePredicate.same_context(
                    channel=author.dm_channel, user=author
                ),
                timeout=45,
            )
        except asyncio.TimeoutError:
            await author.send(_("You took too long to select. Try again later."))
            return None

        try:
            message = int(message.content.strip())
            guild = guilds[message - 1]
        except (ValueError, IndexError):
            await author.send(_("That wasn't a valid choice."))
            return None
        else:
            return guild

    async def send_report(
        self,
        ctx: commands.Context,
        msg: Union[discord.Message, str],
        guild: discord.Guild,
        anonymous=False,
    ):

        msg_obj = isinstance(msg, discord.Message)
        author = guild.get_member(msg.author.id if msg_obj else ctx.author_id)
        report = msg.clean_content if msg_obj else msg

        channel_id = await self.config.guild(guild).output_channel()
        channel = guild.get_channel(channel_id)
        if channel is None:
            return None

        files: List[discord.File] = (
            (await Tunnel.files_from_attach(msg)) if msg_obj else []
        )

        ticket_number = await self.config.guild(guild).next_ticket()
        await self.config.guild(guild).next_ticket.set(ticket_number + 1)

        title = _("Report from {author}{maybe_nick}").format(
            author=author, maybe_nick=(f" ({author.nick})" if author.nick else "")
        )
        if anonymous:
            title = _("Anonymous report")
        desc = report
        report_url = None
        if (
            not anonymous
            and isinstance(ctx.channel, discord.abc.GuildChannel)
            and ctx.channel.guild == guild
        ):
            try:
                async for message in ctx.channel.history(
                    limit=1, before=msg.created_at if msg_obj else None
                ):
                    report_url = message.jump_url
            except discord.errors.Forbidden:
                pass
        if await self.bot.embed_requested(channel, author):
            embed_colour = await (
                ctx.embed_colour()
                if hasattr(ctx, "embed_colour")
                else self.bot.get_embed_colour(ctx.channel)
            )
            if report_url:
                desc += f"\n[report made here]({report_url})"
            em = discord.Embed(description=desc, colour=embed_colour)
            em.set_author(
                name=title,
                icon_url=author.avatar_url
                if not anonymous
                else "https://cdn.discordapp.com/attachments/826191787991367721/826203765467381780/unknown.png",
            )
            footer = _("Report #{}").format(ticket_number)
            if not anonymous:
                footer += f" | User ID: {author.id}"
            em.set_footer(text=footer)
            send_content = None
        else:
            em = None
            send_content = title
            send_content += "\n" + desc + ("\n" + report_url if report_url else "")

        try:
            await Tunnel.message_forwarder(
                destination=channel, content=send_content, embed=em, files=files
            )
        except (discord.Forbidden, discord.HTTPException):
            return None

        await self.config.custom("REPORT", guild.id, ticket_number).report.set(
            {"user_id": author.id, "report": report}
        )
        return ticket_number

    @commands.group(name="report", invoke_without_command=True)
    async def report(self, ctx: commands.Context, *, _report: str = ""):
        """Send a report.

        Use without arguments for interactive reporting, or do
        `[p]report <text>` to use it non-interactively.
        """
        if ctx.guild:
            await ctx.send(
                "Please use this command in DMs with the bot (or use the /report version)."
            )
            return
        return await self._report(ctx=ctx, _report=_report, anonymous=False)

    @commands.group(name="reportanon", invoke_without_command=True)
    async def reportanon(self, ctx: commands.Context, *, _report: str = ""):
        """Send a report anonymously.

        Use without arguments for interactive reporting, or do
        `[p]report <text>` to use it non-interactively.
        """
        if ctx.guild:
            await ctx.send(
                "Please use this command in DMs with the bot (or use the /report version)."
            )
            return
        return await self._report(ctx=ctx, _report=_report, anonymous=True)

    async def _report(
        self,
        ctx: commands.Context,
        *,
        _report: str = "",
        anonymous=False,
        default_guild=None,
        reply_command=None,
    ):
        if reply_command is None:
            reply_command = lambda x: author.send(x)

        author = ctx.author
        guild = ctx.guild
        if guild is None:
            if default_guild is not None:
                guild = default_guild
            else:
                guild = await self.discover_guild(
                    author, prompt=_("Select a server to make a report in by number.")
                )
        if guild is None:
            return False
        g_active = await self.config.guild(guild).active()
        if not g_active:
            await reply_command(_("Reporting has not been enabled for this server"))
            return False
        if guild.id not in self.antispam:
            self.antispam[guild.id] = {}
        if author.id not in self.antispam[guild.id]:
            self.antispam[guild.id][author.id] = AntiSpam(self.intervals)
        if self.antispam[guild.id][author.id].spammy:
            await reply_command(
                _(
                    "You've sent too many reports recently. "
                    "Please contact a server admin if this is important matter, "
                    "or please wait and try again later."
                )
            )
            return False
        if author.id in self.user_cache:
            await reply_command(
                _(
                    "Please finish making your prior report before trying to make an "
                    "additional one!"
                )
            )
            return False
        self.user_cache.append(author.id)

        if _report:
            _m = _report
            if ctx.message:
                _m = copy(ctx.message)
                _m.content = _report
                _m.content = _m.clean_content
            val = await self.send_report(ctx, _m, guild, anonymous=anonymous)
        else:
            try:
                anon_message = (
                    "This report **IS" + ("" if anonymous else " NOT") + "** anonymous."
                )
                await reply_command(
                    _(
                        "Please respond to this message with your Report.{anon_message}"
                        "\nYour report should be a single message"
                    ).format(anon_message=_(anon_message))
                )
            except discord.Forbidden:
                await ctx.send(_("This requires DMs enabled."))
                return False

            try:
                message = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(ctx, channel=author.dm_channel),
                    timeout=180,
                )
            except asyncio.TimeoutError:
                await reply_command(_("You took too long. Try again later."))
                return False
            else:
                val = await self.send_report(ctx, message, guild, anonymous=anonymous)

        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
            if val is None:
                if await self.config.guild(guild).output_channel() is None:
                    await reply_command(
                        _(
                            "This server has no reports channel set up. Please contact a server admin."
                        )
                    )
                else:
                    await reply_command(
                        _(
                            "There was an error sending your report, please contact a server admin."
                        )
                    )
            else:
                await reply_command(
                    _("Your report was submitted. (Ticket #{})").format(val)
                )
                self.antispam[guild.id][author.id].stamp()
        return True

    @reportanon.after_invoke
    async def reportanon_cleanup(self, ctx: commands.Context):
        if not ctx.guild:
            await self._report_cleanup(ctx)

    @report.after_invoke
    async def report_cleanup(self, ctx: commands.Context):
        if not ctx.guild:
            await self._report_cleanup(ctx)

    async def _report_cleanup(self, ctx: commands.Context):
        """
        The logic is cleaner this way
        """
        if ctx.author.id in self.user_cache:
            self.user_cache.remove(ctx.author.id)
        if ctx.guild and ctx.invoked_subcommand is None:
            if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                try:
                    await ctx.message.delete()
                except discord.NotFound:
                    pass

    async def _report_slash(self, ctx: SlashContext, report: str, anonymous: bool):
        try:
            result = await self._report(
                ctx=ctx,
                _report=report,
                anonymous=anonymous,
                default_guild=self.default_guild,
                reply_command=lambda x: ctx.send(x, hidden=True),
            )
            if ctx.author.id in self.user_cache:
                self.user_cache.remove(ctx.author.id)
        except Exception as e:
            import traceback

            await ctx.send("Something broke, sorry!", hidden=True)
            return await ctx.bot.send_to_owners(traceback.format_exc())

    @cog_slash(name="report", description="Report something to the administrators. Use in-game adminhelp instead for in-game matters.")
    async def slash_report(self, ctx: SlashContext, report: str):
        await self._report_slash(ctx, report, False)

    @cog_slash(
        name="reportanon",
        description="Report something to the administrators anonymously.",
    )
    async def slash_reportanon(self, ctx: SlashContext, report: str):
        await self._report_slash(ctx, report, True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        oh dear....
        """

        if not str(payload.emoji) == "\N{NEGATIVE SQUARED CROSS MARK}":
            return

        _id = payload.message_id
        t = next(filter(lambda x: _id in x[1]["msgs"], self.tunnel_store.items()), None)

        if t is None:
            return
        guild = t[0][0]
        tun = t[1]["tun"]
        if payload.user_id in [x.id for x in tun.members]:
            await set_contextual_locales_from_guild(self.bot, guild)
            close_msg = "The user has closed the correspondence."
            if payload.user_id == tun.sender.id:
                close_msg = "The administrator has closed the correspondence."
                await tun.origin.send("You have closed the correspondence.")
            else:
                await tun.recipient.send("You have closed the correspondence.")
            await tun.react_close(uid=payload.user_id, message=_(close_msg))
            self.tunnel_store.pop(t[0], None)

            t = None
            gc.collect()  # lol

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        to_remove = []

        for k, v in self.tunnel_store.items():

            guild, ticket_number = k
            if await self.bot.cog_disabled_in_guild(self, guild):
                to_remove.append(k)
                continue

            await set_contextual_locales_from_guild(self.bot, guild)
            topic = _("Re: ticket# {ticket_number} in {guild.name}").format(
                ticket_number=ticket_number, guild=guild
            )
            # Tunnels won't forward unintended messages, this is safe
            msgs = await v["tun"].communicate(message=message, topic=topic)
            if msgs:
                self.tunnel_store[k]["msgs"] = msgs

        for key in to_remove:
            if tun := self.tunnel_store.pop(key, None):
                guild, ticket = key
                await set_contextual_locales_from_guild(self.bot, guild)
                await tun["tun"].close_because_disabled(
                    _(
                        "Correspondence about ticket# {ticket_number} in "
                        "{guild.name} has been ended due "
                        "to reports being disabled in that server."
                    ).format(ticket_number=ticket, guild=guild)
                )

    @checks.admin_or_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.group(name="tickets")
    async def tickets(self, ctx: commands.Context):
        """Manage Tickets."""
        pass

    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    @tickets.command(name="deanon")
    async def deanon(self, ctx, ticket_number: int):
        """Uncovers the author of an anonymous report."""
        guild = ctx.guild
        channel_id = await self.config.guild(guild).output_channel()
        if ctx.channel.id != channel_id:
            return await ctx.send(f"Go to <#{channel_id}> to use this command.")
        rec = await self.config.custom("REPORT", guild.id, ticket_number).report()

        try:
            user = guild.get_member(rec.get("user_id"))
        except KeyError:
            return await ctx.send(_("That ticket doesn't seem to exist"))

        if user is None:
            return await ctx.send(_("That user isn't here anymore."))

        log.info(
            f"Deanonymization: {ctx.author}({ctx.author.id}) deanonymized ticket {ticket_number} in guild {guild}({guild.id}). The result was {user}({user.id})."
        )

        return await ctx.send(
            _(
                "Report {ticket} was sent by {user}{maybe_nick} ({id}). Deanonymization done by {author} ({author_id})."
            ).format(
                ticket=ticket_number,
                user=user,
                maybe_nick=(f" ({user.nick})" if user.nick else ""),
                id=user.id,
                author=ctx.author,
                author_id=ctx.author.id,
            )
        )

    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    @report.command(name="interact")
    async def interact(self, ctx, ticket_number: int):
        """Used to be for responding to user reports.

        Deprecated. Use [p]respond instead
        """
        return await ctx.send("Deprecated. Use the `respond` command instead.")

    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(name="respond")
    async def respond(
        self, ctx, ticket_number: Optional[int], *, first_msg: Optional[str]
    ):
        """Open a message tunnel.

        This tunnel will forward things you say in this channel
        to the ticket opener's direct messages.
        If ticket_number is not given responds to the last ticket.

        Tunnels do not persist across bot restarts.
        """

        guild = ctx.guild
        channel_id = await self.config.guild(guild).output_channel()
        if ctx.channel.id != channel_id:
            return await ctx.send(f"Go to <#{channel_id}> to use this command.")

        if ticket_number is None:
            ticket_number = (await self.config.guild(guild).next_ticket()) - 1
        rec = await self.config.custom("REPORT", guild.id, ticket_number).report()

        try:
            user = guild.get_member(rec.get("user_id"))
        except KeyError:
            return await ctx.send(_("That ticket doesn't seem to exist"))

        if user is None:
            return await ctx.send(_("That user isn't here anymore."))

        tun = Tunnel(recipient=user, origin=ctx.channel, sender=ctx.author)

        if tun is None:
            return await ctx.send(
                _(
                    "Either you or the user you are trying to reach already "
                    "has an open communication."
                )
            )

        big_topic = _(
            " Anything you say or upload here "
            "will be forwarded to them until the communication is closed.\n"
            "You can close a communication at any point by reacting with "
            "the \N{NEGATIVE SQUARED CROSS MARK} to the last message received.\n"
            "Any message successfully forwarded will be marked with "
            "\N{WHITE HEAVY CHECK MARK}.\n"
            "Tunnels are not persistent across bot restarts."
        )
        topic = (
            _(
                "A administrator in the server `{guild.name}` has opened a 2-way communication about "
                "ticket number {ticket_number}."
            ).format(guild=guild, ticket_number=ticket_number)
            + big_topic
        )
        try:
            m = await tun.communicate(
                message=ctx.message, topic=topic, skip_message_content=True
            )
        except discord.Forbidden:
            await ctx.send(_("That user has DMs disabled."))
        else:
            if first_msg:
                topic = (
                    _("Re: ticket# {ticket_number} in {guild.name}").format(
                        ticket_number=ticket_number, guild=guild
                    )
                    + "\n"
                    + first_msg
                )
                m += await tun.communicate(
                    message=ctx.message, topic=topic, skip_message_content=True
                )
            self.tunnel_store[(guild, ticket_number)] = {"tun": tun, "msgs": m}
            await ctx.send(
                _(
                    "You have opened a 2-way communication about ticket number {ticket_number}."
                ).format(ticket_number=ticket_number)
                + big_topic
            )
