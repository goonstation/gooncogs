from redbot.core import commands, checks, app_commands, Config
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
import discord
import datetime
from typing import *
from .request import GoonhubRequest
from .utilities import servers_autocomplete_all, servers_autocomplete
import logging

class GoonhubTestmerges(commands.Cog):
    def __init__(self, Goonhub):
        self.Goonhub = Goonhub
        self.config = Config.get_conf(self, 1482189223516)
        self.config.register_global(testmerge_channels={})

    @commands.hybrid_group(name="tm", aliases=["testmerge"])
    @checks.admin()
    async def tmgroup(self, ctx: commands.Context):
        """Manage testmerges."""
        pass

    @tmgroup.command(name="list")
    @app_commands.describe(
        server = "The server to show testmerges for (Optional: default shows all servers)",
    )
    @app_commands.autocomplete(server=servers_autocomplete)
    async def list(self, ctx: commands.Context, server: Optional[str]):
        """List active testmerges on a given server or globally."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        server_id = None
        repo = await self.Goonhub.config.repo()
        if server:
            server = goonservers.resolve_server(server)
            if not server: return await ctx.reply("Unknown server.")
            server_id = server.tgs

        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        res = None
        try:
            params = { 'per_page': 100 }
            if server_id is not None:
                params['filters[server]'] = server_id
            res = await req.get('game-build-test-merges', params = params)
            res = res.get('data')
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        
        data = []
        for testmerge in res:
            if testmerge['created_at']:
                testmerge['created_at'] = datetime.datetime.strptime(testmerge['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if testmerge['updated_at']:
                testmerge['updated_at'] = datetime.datetime.strptime(testmerge['updated_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            def similar(a, b):
                if isinstance(a, datetime.date) and isinstance(b, datetime.date):
                    return abs((a - b).total_seconds()) <= 60 * 30
                else:
                    return a == b
            if data and all(similar(data[-1][key], testmerge[key]) for key in testmerge if key != 'server_id' and key != 'id'):
                data[-1]['servers'].append(testmerge['server_id'])
            else:
                data.append(testmerge)
                data[-1]['servers'] = [testmerge['server_id']]

        current_embed = discord.Embed(
                title = f"Testmerges of {server.short_name}" if server else "Testmerges",
                color = await ctx.embed_colour(),
                description = "",
            )
        current_embed_size = len(current_embed.title)
        pages = []
        pr_links = set()
        
        if not data:
            current_embed.description = "_None found_"

        for testmerge in data:
            text_to_add = ""
            pr_link = f"https://github.com/{repo}/pull/{testmerge['pr_id']}"
            pr_links.add(pr_link)
            text_to_add += f"[{testmerge['pr_id']}]({pr_link})"
            if testmerge['server_id']:
                text_to_add += " on " + ", ".join(testmerge['servers'])
            else:
                text_to_add += " on all servers"
            if testmerge['added_by']:
                text_to_add += f" by <@{await spacebeecentcom.ckey_to_discord(testmerge['added_by']['ckey'])}>"
            if testmerge['created_at']:
                text_to_add += f" on <t:{int(testmerge['created_at'].timestamp())}:f>"
            if testmerge['commit']:
                text_to_add += f" [{testmerge['commit'][:7]}](https://github.com/{repo}/pull/{testmerge['pr_id']}/commits/{testmerge['commit']})"
            text_to_add += "\n"
            if testmerge['updated_by'] or testmerge['updated_at']:
                text_to_add += "\N{No-Break Space}" * 5
                text_to_add += "updated"
                if testmerge['updated_by']:
                    text_to_add += f" by <@{await spacebeecentcom.ckey_to_discord(testmerge['updated_by']['ckey'])}>"
                if testmerge['updated_at']:
                    text_to_add += f" on <t:{int(testmerge['updated_at'].timestamp())}:f>"
                text_to_add += "\n"
            if current_embed_size + len(text_to_add) >= 4000:
                pages.append(current_embed)
                current_embed_size = 0
                current_embed = None
            if current_embed is None:
                current_embed = discord.Embed(
                        title = f"Testmerges of {server.short_name}" if server else "Testmerges",
                        color = await ctx.embed_colour(),
                        description = "",
                    )
                current_embed_size += len(current_embed.title)
            current_embed_size += len(text_to_add)
            current_embed.description += text_to_add

        if current_embed:
            pages.append(current_embed)
        for i, page in enumerate(pages):
            page.set_footer(text=f"{i+1}/{len(pages)}")
        if not pages:
            return await ctx.reply(f":warning: Something went wrong")
        if len(pages) > 1:
            # TODO PR embeds
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
        else:
            await ctx.reply(embed=pages[0])
            
    @tmgroup.command(name="merge")
    @app_commands.describe(
        pr = "The pull request ID to merge",
        server = "The server to apply this merge to (Optional: default applies to all servers)",
        commit = "The desired full commit hash of the pull request to merge (Optional: default applies the latest commit)"
    )
    @app_commands.autocomplete(server=servers_autocomplete_all)
    async def merge(self, ctx: commands.Context, pr: int, server: Optional[str], commit: Optional[str]):
        """Testmerges a given PR number at the latest or given GitHub commit to a given server or globally."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        servers = goonservers.servers
        if server:
            servers = goonservers.resolve_server_or_category(server)
            if not servers: return await ctx.reply("Unknown server.")
        server_ids = [server.tgs for server in servers]
            
        if commit and len(commit) != 40:
            return await ctx.reply(f":warning: That is not a full commit hash")
        
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        try:
            data = {
                'game_admin_ckey': author_ckey,
                'pr_id': pr,
                'server_ids': server_ids
            }
            if commit: data['commit'] = commit
            await req.post('game-build-test-merges', data = data)
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        
        await self.testmerge_announce("\N{White Heavy Check Mark} **New** testmerge", pr=pr, servers=servers, commit=commit)
            
        if ctx.interaction:
            await ctx.reply(f"\N{WHITE HEAVY CHECK MARK} Success - note that this does not retrigger a build")
        else:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            await ctx.send("Success - note that this does not retrigger a build")
            
    @tmgroup.command(name="update")
    @app_commands.describe(
        pr = "The pull request ID to merge",
        server = "The server to apply this merge to (Optional: default applies to all servers)",
        commit = "The desired full commit hash of the pull request to merge (Optional: default applies the latest commit)"
    )
    @app_commands.autocomplete(server=servers_autocomplete_all)
    async def update(self, ctx: commands.Context, pr: int, server: Optional[str], commit: Optional[str]):
        """Updates a given testmerge to the latest or given GitHub commit on a given server or globally."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        servers = goonservers.servers
        if server:
            servers = goonservers.resolve_server_or_category(server)
            if not servers: return await ctx.reply("Unknown server.")
            
        if commit and len(commit) != 40:
            return await ctx.reply(f":warning: That is not a full commit hash")
        
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        
        existingTestMerges = []
        try:
            res = await req.get('game-build-test-merges', params = { 'filters[pr]': pr })
            existingTestMerges = res.get('data')
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        
        if not existingTestMerges:
            return await ctx.reply(f":warning: There are no testmerges for that pull request!")
        
        updatingServers = []
        updatingTestMerges = []
        for testMerge in existingTestMerges:
            if servers:
                for server in servers:
                    if server.tgs == testMerge['server_id']:
                        updatingTestMerges.append(testMerge)
                        updatingServers.append(server)
                        break
            else:
                updatingTestMerges.append(testMerge)
                for server in servers:
                    if server.tgs == testMerge['server_id']:
                        updatingServers.append(server)
                        break
                
        if not updatingTestMerges:
            return await ctx.reply(f":warning: There are no testmerges for that pull request on those servers!")
        
        errors = []
        for testMerge in updatingTestMerges:
            try:
                data = { 'game_admin_ckey': author_ckey, 'pr_id': pr }
                if commit: data['commit'] = commit
                await req.put(f"game-build-test-merges/{testMerge['id']}", data = data)
            except Exception as e:
                errors.append(f"[{testMerge['server_id']}] {e}")
                continue
            
        await self.testmerge_announce("\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} **Updated** testmerge", pr=pr, servers=updatingServers, commit=commit)
            
        if ctx.interaction:
            await ctx.reply(f"\N{WHITE HEAVY CHECK MARK} Success - note that this does not retrigger a build")
        else:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            await ctx.send("Success - note that this does not retrigger a build")
            
    @tmgroup.command(name="cancel")
    @app_commands.autocomplete(server=servers_autocomplete_all)
    @app_commands.describe(
        pr = "The pull request ID to merge",
        server = "The server to cancel this merge on (Optional: default applies to all servers)",
    )
    async def cancel(self, ctx: commands.Context, pr: int, server: Optional[str]):
        """Cancels a given testmerge on a given server or globally."""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        servers = goonservers.servers
        if server:
            servers = goonservers.resolve_server_or_category(server)
            if not servers: return await ctx.reply("Unknown server.")
            
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
            
        existingTestMerges = []
        try:
            res = await req.get('game-build-test-merges', params = { 'filters[pr]': pr })
            existingTestMerges = res.get('data')
        except Exception as e:
            return await ctx.reply(f":warning: {e}")
        
        if not existingTestMerges:
            return await ctx.reply(f":warning: There are no testmerges for that pull request!")
        
        removingFromServers = []
        removingTestMerges = []
        for testMerge in existingTestMerges:
            if servers:
                for server in servers:
                    if server.tgs == testMerge['server_id']:
                        removingFromServers.append(server)
                        removingTestMerges.append(testMerge)
                        break
            else:
                removingTestMerges.append(testMerge)
                for server in servers:
                    if server.tgs == testMerge['server_id']:
                        removingFromServers.append(server)
                        break
                
        if not removingTestMerges:
            return await ctx.reply(f":warning: There are no testmerges for that pull request on those servers!")
        
        errors = []
        for testMerge in removingTestMerges:
            try:
                await req.delete(f"game-build-test-merges/{testMerge['id']}")
            except Exception as e:
                errors.append(f"[{testMerge['server_id']}] {e}")
                continue

        await self.testmerge_announce("\N{CROSS MARK} **Cancelled** testmerge", pr=pr, servers=removingFromServers)

        if ctx.interaction:
            await ctx.reply(f"\N{WHITE HEAVY CHECK MARK} Success - note that this does not retrigger a build")
        else:
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
            await ctx.send("Success - note that this does not retrigger a build")
            
    @tmgroup.command()
    async def addchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Subscribe a channel to receive testmerge updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.testmerge_channels() as channels:
            channels[str(channel.id)] = None
        await ctx.reply(
            f"Channel {channel.mention} will now receive notifications about testmerges."
        )

    @tmgroup.command()
    async def removechannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Unsubscribe a channel from testmerge updates."""
        if channel is None:
            channel = ctx.channel
        async with self.config.testmerge_channels() as channels:
            del channels[str(channel.id)]
        await ctx.reply(
            f"Channel {channel.mention} will no longer receive notifications about testmerges."
        )

    @tmgroup.command()
    async def checkchannels(self, ctx: commands.Context):
        """Check channels subscribed to testmerge updates."""
        channel_ids = await self.config.testmerge_channels()
        if not channel_ids:
            await ctx.reply("No channels.")
        else:
            await ctx.reply(
                "\n".join(self.Goonhub.bot.get_channel(int(ch)).mention for ch in channel_ids)
            )
            
    async def testmerge_announce(self, message: str, pr: int, servers: List[Any], commit: Optional[str] = None):
        channels = await self.config.testmerge_channels()
        if not len(channels):
            return
        repo = await self.Goonhub.config.repo()
        msg = message + "\n"
        msg += f"https://github.com/{repo}/pull/{pr}\n"
        if commit:
            msg += f"on commit https://github.com/{repo}/pull/{pr}/commits/{commit}"
        if len(servers):
            msg += "on servers "
            for server in servers:
                msg += server.short_name + " "
        for channel_id in channels:
            channel = self.Goonhub.bot.get_channel(int(channel_id))
            if channel:
                await channel.send(msg)
