import asyncio
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
import datetime

class RoleStuff(commands.Cog):

    default_user_settings = {"last_roles": {}}
    LETS_TALK_TIMEOUT = 60 * 60

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=524658401248992)
        self.config.register_user(**self.default_user_settings)

        self.lets_talk_timeout_task = None
        self.suppress_next_lets_chat_role_removal_message = False

    @property
    def admin_channel(self):
        return self.bot.get_channel(182254222694285312)

    @property
    def debug_channel(self):
        return self.bot.get_channel(412381738510319626)

    @property
    def lets_chat_channel(self):
        return self.bot.get_channel(683769319259111549)

    @property
    def lets_chat_role(self):
        channel = self.lets_chat_channel
        if channel:
            return channel.guild.get_role(683768446680563725)

    @property
    def player_role(self):
        channel = self.lets_chat_channel
        if channel:
            return channel.guild.get_role(182284445837950977)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        user_data = await self.config.user(member).last_roles()
        if len(member.roles) > 1:
            user_data[str(member.guild.id)] = [role.id for role in member.roles][1:]
            await self.config.user(member).last_roles.set(user_data)

    async def remove_lets_chat_role_after_time(self, time: int, member: discord.Member):
        await asyncio.sleep(time)
        while True:
            last_msg = self.lets_chat_channel.last_message
            if last_msg is None:
                break
            sleep_time = time - (datetime.datetime.now() - last_msg.created_at).total_seconds()
            if sleep_time <= 0:
                break
            await asyncio.sleep(sleep_time)
        if self.lets_chat_role in member.roles:
            try:
                await member.remove_roles(self.lets_chat_role, reason="timeout")
                await self.lets_chat_channel.send(
                    f"Automatically removing {self.lets_chat_role.mention} from {member.mention} because its duration ({self.LETS_TALK_TIMEOUT / 60:.0f} minutes) expired."
                )
            except discord.errors.NotFound:
                await self.lets_chat_channel.send(
                    f"Tried to remove {self.lets_chat_role.mention} from {member.mention} because its duration ({self.LETS_TALK_TIMEOUT / 60:.0f} minutes) expired but they already left the server."
                )
            except:
                import traceback

                return await self.bot.send_to_owners(traceback.format_exc())

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if (
            self.lets_chat_role in after.roles
            and self.lets_chat_role not in before.roles
        ):
            dm_channel = after.dm_channel
            if dm_channel is None:
                dm_channel = await after.create_dm()
            for member in self.lets_chat_role.members:
                if member != after:
                    self.suppress_next_lets_chat_role_removal_message = True
                    await member.remove_roles(
                        self.lets_chat_role, reason="someone else entering Let's Chat"
                    )
                    await self.admin_channel.send(
                        f"Automatically removing {self.lets_chat_role.mention} from {member.mention} because {after.mention} is now being talked to."
                    )
            # await self.debug_channel.send(f"{after.mention} now has role {self.lets_chat_role.mention}, total number of people with this role: {len(self.lets_chat_role.members)}")
            await after.remove_roles(self.player_role, reason=f"entering Let's Chat")
            em = discord.Embed(
                description=f"Beginning conversation with {after.mention}",
                colour=discord.Colour.from_rgb(80, 140, 80),
            )
            em.set_footer(text=f"{after.id}")
            await self.lets_chat_channel.send(embed=em)
            self.lets_talk_timeout_task = asyncio.create_task(
                self.remove_lets_chat_role_after_time(self.LETS_TALK_TIMEOUT, after)
            )
            try:
                result = await dm_channel.send(
                    f"""Hi! An admin in the Goonstation Discord would like to talk to you. Please click here <#{self.lets_chat_channel.id}> and send a message there so that we know you've seen this. Please don't click away from the channel, or else you'll lose the scrollback. Thank you!\n(If the channel is no longer accessible when you read this message please use the `]report` command to contact admins instead.)"""
                )
            except discord.errors.Forbidden:
                try:
                    await self.lets_chat_channel.send(
                        f"""Hi {after.mention}! An admin would like to talk to you. Please send a message here to know that you've seen this. Please don't click away from the channel, or else you'll lose the scrollback. Thank you!"""
                    )
                except Exception as e:
                    await self.debug_channel.send(
                        "Let's Talk stuff crashed, notify the user yourself!"
                    )
            # await self.lets_chat_channel.edit(name="lets-talk\N{Police Cars Revolving Light}")
        elif (
            self.lets_chat_role not in after.roles
            and self.lets_chat_role in before.roles
        ):
            if self.lets_talk_timeout_task:
                await asyncio.sleep(1)
                self.lets_talk_timeout_task.cancel()
                self.lets_talk_timeout_task = None
            await after.add_roles(self.player_role, reason=f"leaving Let's Chat")
            em = discord.Embed(
                description=f"Ending conversation with {after.mention}",
                colour=discord.Colour.from_rgb(140, 80, 80),
            )
            em.set_footer(text=f"{after.id}")
            if not self.suppress_next_lets_chat_role_removal_message:
                await self.lets_chat_channel.send(embed=em)
            else:
                self.suppress_next_lets_chat_role_removal_message = False
            # await self.lets_chat_channel.edit(name="lets-talk")
            # await self.debug_channel.send(f"{after.mention} lost the role {self.lets_chat_role.mention}, total number of people with this role: {len(self.lets_chat_role.members)}")

    @commands.command()
    @checks.mod_or_permissions(manage_roles=True)
    async def purgeroles(self, ctx: commands.Context, user: discord.User):
        """Clears saved roles of a given user."""
        await self.config.user(user).last_roles.clear()
        await ctx.send("Roles have been wiped out.")

    @commands.command()
    @checks.mod_or_permissions(manage_roles=True)
    async def lastroles(self, ctx: commands.Context, user: discord.User):
        """Shows a list of roles an user had the last time they left the guild."""
        user_data = await self.config.user(user).last_roles()
        guild_id = str(ctx.guild.id)
        if guild_id not in user_data:
            return await ctx.send("Never heard of them.")
        roles = []
        unsuccessful_count = 0
        for role_id in user_data[guild_id]:
            role = ctx.guild.get_role(role_id)
            if role:
                roles.append(role)
            else:
                unsuccessful_count += 1
        reply = ""
        if len(roles) == 0:
            reply += "No existing roles found. "
        else:
            reply += "Last roles: " + ", ".join(role.name for role in roles) + ". "
        if unsuccessful_count > 0:
            reply += f"Number of removed roles they had: {unsuccessful_count}."
        await ctx.send(reply)

    async def restore_roles_internal(self, member: discord.Member, ctx=None):
        user_data = await self.config.user(member).last_roles()
        guild_id = str(member.guild.id)
        if guild_id not in user_data:
            return None, None
        roles_to_add = []
        unsuccessful_count = 0
        for role_id in user_data[guild_id]:
            role = member.guild.get_role(role_id)
            if role == self.lets_chat_role:
                continue
            if role and not role.managed:
                roles_to_add.append(role)
            else:
                unsuccessful_count += 1
        reason = "restored last roles on leaving"
        if ctx:
            reason = f"restored last roles at the request of {ctx.message.author}"
        await member.add_roles(*roles_to_add, reason=reason)
        return roles_to_add, unsuccessful_count

    @commands.command()
    @checks.mod_or_permissions(manage_roles=True)
    async def restoreroles(self, ctx: commands.Context, member: discord.Member):
        """Tries to restore a member's roles to what they had the last time they left."""
        roles_to_add, unsuccessful_count = await self.restore_roles_internal(member)
        if roles_to_add is None:
            return await ctx.send("Never head of them.")
        reply = ""
        if len(roles_to_add) == 0:
            reply += "Restored no roles. "
        else:
            reply += (
                "Restored roles " + ", ".join(role.name for role in roles_to_add) + ". "
            )
        if unsuccessful_count > 0:
            reply += f"Failed to restore {unsuccessful_count} roles."
        await ctx.send(reply)
