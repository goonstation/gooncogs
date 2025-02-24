from redbot.core import commands, checks, app_commands, Config
from typing import *
from .utilities import ckeyify, success_response
from .paginator import PaginatorView
from .request import GoonhubRequest
import logging

class GoonhubNotes(commands.Cog):
    def __init__(self, Goonhub):
        self.Goonhub = Goonhub
        self.config = Config.get_conf(self, 1482189223518)
        self.config.register_global(channels={})

    @commands.hybrid_group(name="notes")
    @checks.admin()
    async def notesgroup(self, ctx: commands.Context):
        """Player notes."""
        pass
    
    async def show_notes(self, ctx: commands.Context, ckey: str, clean=False):
        ckey = ckeyify(ckey)
        view = PaginatorView(
            self.Goonhub,
            ctx.message.author,
            "players/notes",
            params = {
                'filters[ckey]': ckey,
                'filters[exact]': 1
            },
            embed_config = {
                'title': f'Clean notes for {ckey}' if clean else f'Notes for {ckey}',
                'url': '' if clean else await self.Goonhub.build_url(f"admin/players/{ckey}"),
                'color': await ctx.embed_colour()
            }
        )
        
        goonservers = self.Goonhub.bot.get_cog("GoonServers")
        async def build_field(item, timestamps):
            time = timestamps["created_at"]
            if item["updated_at"] and item["updated_at"] != item["created_at"]:
                time += f', updated {timestamps["updated_at"]}'
            
            name = '[All]'
            if item["server_id"]:
                server = goonservers.resolve_server(item["server_id"])
                if server: name = f'[{server.short_name}]'
            name += ':'
            if not clean:
                name += f' {item["game_admin"]["ckey"]}'
            name += f' at {time}'
            
            loglink = ''
            if item["round_id"] and not clean:
                url = await self.Goonhub.build_url(f'admin/logs/{item["round_id"]}')
                loglink = f"[↑]({url}) "
            
            text = f'{loglink}{item["note"]}'
            return { 'name': name, 'text': text }
            
        view.build_field = build_field
            
        embed = await view.fetch_first_page()
        return { 'embed': embed, 'view': view }
    
    @notesgroup.command(name="show")
    @checks.admin()
    @app_commands.describe(ckey="The Byond ckey of the player")
    async def show(self, ctx: commands.Context, ckey: str):
        """Show notes for a player"""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        try:
            res = await self.show_notes(ctx, ckey)
            res['view'].message = await ctx.reply(embed=res['embed'], view=res['view'])
        except Exception as e:
            await ctx.reply(f"{e}")
            
    @notesgroup.command(name="clean")
    @checks.admin()
    @app_commands.describe(ckey="The Byond ckey of the player")
    async def clean(self, ctx: commands.Context, ckey: str):
        """Show notes for a player but stripped of admin names"""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        try:
            res = await self.show_notes(ctx, ckey, clean=True)
            res['view'].message = await ctx.reply(embed=res['embed'], view=res['view'])
        except Exception as e:
            await ctx.reply(f"{e}")
            
    @notesgroup.command(name="add")
    @checks.admin()
    @app_commands.describe(ckey="The Byond ckey of the player", note="The note to add")
    async def add(self, ctx: commands.Context, ckey: str, note: str):
        """Add a note to a player"""
        await ctx.defer() if ctx.interaction else await ctx.typing()
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        
        spacebeecentcom = self.Goonhub.bot.get_cog("SpacebeeCentcom")
        author_ckey = await spacebeecentcom.get_ckey(ctx.author)
        if author_ckey is None:
            return await ctx.reply("Your account needs to be linked to use this")
        
        try:
            await req.post('players/notes', data = {
                'game_admin_ckey': author_ckey,
                'ckey': ckeyify(ckey),
                'note': note
            })
            await success_response(ctx)
        except Exception as e:
            await ctx.reply(f":warning: {e}")
        