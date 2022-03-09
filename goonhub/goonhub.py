import asyncio
import aiohttp
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
from geoip import geolite2
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.chat_formatting import pagify, box, quote
import datetime
import unicodedata
import inspect
import urllib.parse
import uuid
import time

class GoonHub(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.cancelled_findalts = False
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.cancel())

    def country_to_emoji(self, country):
        if country and len(country) == 2:
            try:
                return ''.join(unicodedata.lookup("regional indicator symbol letter " + c) for c in country)
            except KeyError:
                return None
        return None

    def ckeyify(self, text):
        return ''.join(c.lower() for c in text if c.isalnum())

    async def query_user_search(self, q, exact=False):
        tokens = await self.bot.get_shared_api_tokens('goonhub')
        api_key = tokens['playernotes_api_key']
        mod_q = q.replace('%%', '%%%').replace('\\', '')
        url = f"{tokens['playernotes_url']}/?auth={api_key}&action=search_users&format=json&victim={mod_q}"
        if exact:
            url += "&exact=1"
        async with self.session.get(url) as res:
            if res.status != 200:
                return res
            return await res.json(content_type='text/html')

    @checks.admin()
    @commands.command()
    async def cancelfindalts(self, ctx: commands.Context):
        self.cancelled_findalts = True

    @checks.admin()
    @commands.command()
    @commands.cooldown(3, 3)
    @commands.max_concurrency(1, wait=False)
    async def findalts(self, ctx: commands.Context, *, target_ckey: str):
        self.cancelled_findalts = False
        queue = [self.ckeyify(target_ckey)]
        graph_edges = set()
        graph_nodes = set()
        output_msg = await ctx.send(f"Alts of {target_ckey}:\n[Initializing]")
        ckeys = []
        last_edit = time.time()
        async def update_msg(position, finished=False):
            nonlocal output_msg, ckeys, last_edit
            if not finished and time.time() - last_edit < 2.5:
                return
            last_edit = time.time()
            text = f"Alts of {target_ckey}:\n" + "\n".join(ckeys) + "\n"
            if finished:
                text += f"[Finished {position}]"
                reply = f"Search for {target_ckey}'s alts finished:\n{output_msg.jump_url}"
                generalapi = self.bot.get_cog("GeneralApi")
                if generalapi:
                    file_lines = ["graph {", "node [style=filled]"]
                    ckeyckey = self.ckeyify(target_ckey)
                    for node in graph_nodes:
                        attr = []
                        if node.startswith("ckey"):
                            _, ckey = node.split('_')
                            if ckey == ckeyckey:
                                attr.append("color = red")
                            else:
                                attr.append("color = \"#ffcccc\"")
                            attr.append(f"label = \"{ckey}\"")
                        elif node.startswith("cid"):
                            _, cid = node.split('_')
                            attr.append("color = \"#ccffcc\"")
                            attr.append(f"label = \"{cid}\"")
                        elif node.startswith("ip"):
                            ip_parts = node.split('_')
                            attr.append("color = \"#ccccff\"")
                            attr.append(f"label = \"{'.'.join(ip_parts[1:])}\"")
                        file_lines.append(f"{node} [{','.join(attr)}]")
                    file_lines.extend(f"{a} -- {b}" for a, b in graph_edges)
                    file_lines.append("}")
                    file_text = "\n".join(file_lines)
                    fname = f"{self.ckeyify(target_ckey)}_{uuid.uuid4()}.dot"
                    file_folder = generalapi.static_path / "gv"
                    file_folder.mkdir(exist_ok=True)
                    with open(file_folder / fname, 'w') as f:
                        f.write(file_text)
                    file_url = f"https://medass.pali.link/static/gv/{fname}"
                    gv_url = "https://pali.link/graphviz/?url=" + urllib.parse.quote(file_url)
                    reply += "\n" + gv_url
                await ctx.reply(reply)
            else:
                text += f"[Working... {position}/{len(queue)}?]\nuse `]cancelfindalts` to cancel early"
            await output_msg.edit(content=text)
        for i, query in enumerate(queue):
            await update_msg(i + 1, False)
            data = await self.query_user_search(query, exact=True)
            for info in data:
                if query not in info.values():
                    await ctx.send(f"WARNING: Query `{query}` resulted in `{info}` which doesn't contain the query.")
                ip_node = "ip_" + info['ip'].replace('.', '_')
                cid_node = "cid_" + info['compid']
                ckey_node = "ckey_" + info['ckey']
                graph_nodes |= {ip_node, cid_node, ckey_node}
                graph_edges.add((ckey_node, cid_node))
                graph_edges.add((ckey_node, ip_node))
                graph_edges.add((ip_node, cid_node))
                for k in ["ckey", "ip", "compid"]:
                    if info[k] not in queue:
                        queue.append(info[k])
                if info['ckey'] not in ckeys:
                    ckeys.append(info['ckey'])
            if not isinstance(data, list):
                await update_msg("- Error", True)
                return
            if len(ckeys) > 100:
                await update_msg("- Too Many Ckeys", True)
                return
            if self.cancelled_findalts:
                await update_msg("- Cancelled", True)
                return
        await update_msg(len(queue), True)

    @checks.admin()
    @commands.command()
    async def investigate(self, ctx: commands.Context, target_ckey: str):
        """Investigates a given ckey.

        Prefix the ckey with ! to do an exact search."""
        embed_colour = await ctx.embed_colour()
        current_embed = None
        pages = []
        exact = False
        if len(target_ckey) and target_ckey[0] == "!":
            exact = True
            target_ckey = target_ckey[1:]
        with ctx.typing():
            data = await self.query_user_search(target_ckey, exact)
            if not isinstance(data, list):
                await ctx.send(f"Error code {data.status} occured when querying the API")
                return
            for info in data:
                if current_embed and len(current_embed.fields) >= 12:
                    pages.append(current_embed)
                    current_embed = None
                if current_embed is None:
                    current_embed = discord.Embed(
                            title = f"Investigating `{target_ckey or ' '}`",
                            color = embed_colour,
                        )
                ip_info = None
                try:
                    ip_info = geolite2.lookup(info['ip'])
                except ValueError:
                    pass
                recorded_date = datetime.datetime.fromisoformat(info['recorded'])
                recorded_date = recorded_date.replace(tzinfo=datetime.timezone.utc)
                message = inspect.cleandoc(f"""
                    IP: {info['ip']}
                    CID: {info['compid']}
                    Date: <t:{int(recorded_date.timestamp())}:F>
                    """).strip()
                if ip_info:
                    message += f"\nCountry: {ip_info.country}"
                    emoji = self.country_to_emoji(ip_info.country)
                    if emoji:
                        message += " " + emoji
                ckey_title = info['ckey']
                if self.ckeyify(ckey_title) == self.ckeyify(target_ckey):
                    ckey_title = "\N{Large Green Circle} " + ckey_title
                else:
                    ckey_title = "\N{Large Yellow Circle} " + ckey_title
                current_embed.add_field(
                        name = f"{ckey_title}",
                        value = message,
                        inline = True
                        )
        if current_embed:
            pages.append(current_embed)
        n_matches = 0
        for i, page in enumerate(pages):
            page.set_footer(text=f"{i+1}/{len(pages)} | results {n_matches + 1} to {n_matches + len(page.fields)}")
            n_matches += len(page.fields)
        if not pages:
            await ctx.send("No results found")
            return
        if len(pages) > 1:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
        else:
            await ctx.send(embed=pages[0])

    @commands.command()
    @checks.admin()
    async def notes(self, ctx: commands.Context, *, ckey: str):
        """Lists admin notes of a given ckey."""
        await self._notes(ctx, ckey=ckey, clean=False)

    @commands.command()
    @checks.admin()
    async def cleannotes(self, ctx: commands.Context, *, ckey: str):
        """Lists admin notes of a given ckey but stripped of admin names."""
        await self._notes(ctx, ckey=ckey, clean=True)

    @commands.command()
    @checks.admin()
    async def singlenotes(self, ctx: commands.Context, *, ckey: str):
        """Lists admin notes of a given ckey, now one per page."""
        await self._notes(ctx, ckey=ckey, clean=False, one_per_page=True)

    @commands.command()
    @checks.admin()
    async def addnote(self, ctx: commands.Context, ckey: str, *, note: str):
        ckey = self.ckeyify(ckey)
        data = None
        tokens = await self.bot.get_shared_api_tokens('goonhub')
        api_key = tokens['playernotes_api_key']
        url = f"{tokens['playernotes_url']}/?auth={api_key}&action=add&format=json&server_id=Discord&server=0&ckey={ckey}&akey={ctx.author.name} (Discord)&note={note}"
        with ctx.typing():
            async with self.session.get(url) as res:
                if res.status != 200:
                    await ctx.message.reply(f"Error code {res.status} occured when querying the API")
                    return
                data = await res.text()
        if data is None:
            await ctx.message.reply(f"No response from the server")
            return
        if data.strip() == '{"success":true}':
            await ctx.message.reply(f"Successfully added the following note to ckey {ckey}:\n{quote(note)}")
            return
        await ctx.message.reply("An error likely occurred: ```" + data + "```")

    async def _notes(self, ctx: commands.Context, ckey: str, clean=False, one_per_page=False):
        ckey = self.ckeyify(ckey)
        data = None
        tokens = await self.bot.get_shared_api_tokens('goonhub')
        api_key = tokens['playernotes_api_key']
        url = f"{tokens['playernotes_url']}/?auth={api_key}&action=get&format=json&ckey={ckey}"
        with ctx.typing():
            async with self.session.get(url) as res:
                if res.status != 200:
                    await ctx.message.reply(f"Error code {res.status} occured when querying the API")
                    return
                data = await res.json(content_type='text/html')
        if data is None:
            return
        if isinstance(data, dict) and data['error']:
            await ctx.message.reply("Error: " + data['error'])
            return
        pages = []
        embed_colour = await ctx.embed_colour()
        current_embed = None
        current_embed_size = 0
        def add_field(name, value):
            nonlocal current_embed, current_embed_size
            for i, value_part in enumerate(pagify(value, delims=('\n', ' '), priority=True, page_length=1024)):
                field_name = name
                if i == 1:
                    field_name = "..."
                elif i > 1:
                    field_name = f"... ({i})"
                field_size = len(field_name) + len(value_part)
                if current_embed and len(current_embed.fields) >= 25 or field_size + current_embed_size >= 5950:
                    pages.append(current_embed)
                    current_embed = None
                    current_embed_size = 0
                if current_embed is None:
                    current_embed = discord.Embed(
                            title = f"Clean notes of {ckey}" if clean else f"Notes of {ckey}",
                            color = embed_colour,
                        )
                    current_embed_size += len(current_embed.title)
                current_embed_size += field_size
                current_embed.add_field(
                        name = field_name,
                        value = value_part,
                        inline = False,
                        )
            if one_per_page:
                pages.append(current_embed)
                current_embed = None
                current_embed_size = 0
        for note in data:
            timestamp = note['created']
            try:
                date = datetime.datetime.strptime(timestamp, '%b %d %Y %H:%M%p')
                date = date.replace(tzinfo=datetime.timezone.utc)
                timestamp = int(date.timestamp())
                timestamp = f"<t:{timestamp}:F>"
            except ValueError:
                pass
            if clean:
                field_name = f"[{note['server']}] on {timestamp}"
            else:
                field_name = f"[{note['server']}] {note['akey']} on {timestamp}"
            field_value = note['note']
            add_field(field_name, field_value)
        if current_embed:
            pages.append(current_embed)
        for i, page in enumerate(pages):
            page.set_footer(text=f"{i+1}/{len(pages)}")
        if not pages:
            await ctx.send("Something went wrong")
            return
        if len(pages) > 1:
            await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
        else:
            await ctx.send(embed=pages[0])

