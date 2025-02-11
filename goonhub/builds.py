from redbot.core import commands, checks, app_commands, Config
import discord
from typing import *
from .build_hooks import BuildHooks
from .request import GoonhubRequest
from .utilities import servers_autocomplete_all, servers_autocomplete, success_response
import logging

class GoonhubBuilds(commands.Cog):
    def __init__(self, Goonhub):
        self.Goonhub = Goonhub
        self.config = Config.get_conf(self, 1482189223517)
        self.config.register_global(channels={})
        
    def register_to_general_api(self, app):
        BuildHooks(self.config, self.Goonhub, app)

    @commands.hybrid_group(name="ci")
    @checks.admin()
    async def cigroup(self, ctx: commands.Context):
        """Build manager."""
        pass

    @cigroup.command(name="status")
    async def status(self, ctx: commands.Context):
        """Check status of CI builds."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        try:
            res = await req.get('game-builds/status')
            res = res.get('data')
            current_builds = res['current']
            queued_builds = res['queued']
            embed = discord.Embed(
                title = f"Build Status",
                color = await ctx.embed_colour(),
                url = await self.Goonhub.build_url('admin/builds')
            )

            field = []
            for item in current_builds:
                admin = item.get('admin', {})
                server = item.get('server', {})
                build = item.get('build', {})
                url = await self.Goonhub.build_url(f"admin/builds/{build['id']}")
                author = admin['name'] if admin['name'] else admin['ckey']
                field.append(f"[{server['name']}]({url})")
                field.append(f"  _Started by {author} {round(build['duration'])} seconds ago_")
            if not field: field = ['_None_']
            embed.add_field(name="Currently Building", value="\n".join(field), inline=False)

            field = []
            for item in queued_builds:
                admin = item.get('admin', {})
                server = item.get('server', {})
                author = admin['name'] if admin['name'] else admin['ckey']
                field.append(f"{server['name']}")
                field.append(f"  _Queued by {author}_")
            if not field: field = ['_None_']
            embed.add_field(name="Queued Builds", value="\n".join(field), inline=False)

            return await ctx.reply(embed=embed)
        except Exception as e:
            return await ctx.reply(f":warning: {e}")

    @cigroup.command(name="build")
    @app_commands.describe(server = "The server or server group to build")
    @app_commands.autocomplete(server=servers_autocomplete_all)
    async def build(self, ctx: commands.Context, server: str):
        """Build a server or group of servers."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        servers = set(goonservers.resolve_server_or_category(server))
        if not servers: return await ctx.reply("Unknown server.")
        
        success = True
        for server in servers:
            try:
                await req.post('game-builds/build', data = {
                    'game_admin_ckey': author_ckey,
                    'server_id': server.tgs
                })
            except Exception as e:
                success = False
                await ctx.reply(f":warning: {e}")
                continue
        if success:
            await success_response(ctx)
    
    @cigroup.command(name="cancel")
    @app_commands.describe(server = "The server or server group to cancel builds on")
    @app_commands.autocomplete(server=servers_autocomplete)
    async def cancel(self, ctx: commands.Context, server: str):
        """Cancel a build or group of builds"""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        server = goonservers.resolve_server(server)
        if not server: return await ctx.reply("Unknown server.")
        
        try:
            await req.post('game-builds/cancel', data = {
                'game_admin_ckey': author_ckey,
                'server_id': server.tgs
            })
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        await success_response(ctx)

    @cigroup.command(name="branch")
    @app_commands.describe(
        server = "The server or server group to lookup",
        branch = "The branch name to set (Optional)"
    )
    @app_commands.autocomplete(server=servers_autocomplete_all)
    async def branch(self, ctx: commands.Context, server: str, branch: Optional[str]):
        """Gets or sets the branch for a server or group of servers."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        servers = goonservers.resolve_server_or_category(server)
        if not servers: return await ctx.reply("Unknown server.")
        
        repo = await self.Goonhub.config.repo()
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        settings = None
        
        try:
            res = await req.get('game-build-settings', params = { 'per_page': 100 })
            settings = res.get('data')
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        
        if branch:
            for server in servers:
                setting = next((setting for setting in settings if setting["server_id"] == server.tgs), False)
                if not setting: return await ctx.reply(f":warning: No build settings found")
                try:
                    res = await req.put(f"game-build-settings/{setting['id']}", data = { 'branch': branch })
                    res = res.get('data')
                except Exception as e:
                    return await ctx.reply(f":warning: {e}")
            await success_response(ctx)
        else:
            embed = discord.Embed(
                title = "",
                color = await ctx.embed_colour(),
                description = "",
            )
            
            for server in servers:
                setting = next((setting for setting in settings if setting["server_id"] == server.tgs), False)
                if setting:
                    embed.add_field(
                        name=server.short_name,
                        value=f"[{setting['branch']}](https://github.com/{repo}/tree/{setting['branch']})",
                        inline=True
                    )
                    
            await ctx.reply(embed=embed)

    @cigroup.command()
    async def addchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Subscribe a channel to receive CI build updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            channels[str(channel.id)] = None
        await ctx.reply(
            f"Channel {channel.mention} will now receive notifications about builds."
        )

    @cigroup.command()
    async def removechannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Unsubscribe a channel from CI build updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.channels() as channels:
            del channels[str(channel.id)]
        await ctx.reply(
            f"Channel {channel.mention} will no longer receive notifications about builds."
        )

    @cigroup.command()
    async def checkchannels(self, ctx: commands.Context):
        """Check channels subscribed to CI build updates."""
        channel_ids = await self.config.channels()
        if not channel_ids:
            await ctx.reply("No channels.")
        else:
            await ctx.reply(
                "\n".join(self.Goonhub.bot.get_channel(int(ch)).mention for ch in channel_ids)
            )