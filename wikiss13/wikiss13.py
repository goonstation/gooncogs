"""WikiSS13 cog for Red-DiscordBot ported by PhasecoreX and pali6."""
import re

import asyncio
import aiohttp
import discord
from dateutil.parser import isoparse
from redbot.core import __version__ as redbot_version, commands
from redbot.core.utils.chat_formatting import error, warning
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
import Levenshtein
import html
from itertools import chain

__author__ = "PhasecoreX, pali"


class Wikiss13(commands.Cog):
    """Look up stuff on wiki.ss13.co ."""

    DISAMBIGUATION_CAT = "Category:All disambiguation pages"
    WHITESPACE = re.compile(r"[\n\s]{4,}")
    HTML_TAG = re.compile(r"<.*?>", re.DOTALL)
    TOC = re.compile(r'<div id="toc".*?\n</div>\n\n', re.DOTALL)
    IGNORE_STUFF = re.compile(
        r'<table (style|class="wikitable mw-collapsible"|class="wikitable").*?</table>|<label.*?</label>|<div class="thumbcaption.*?</div></div>|<dl>.*?</dl>|<data value="summary hide">.*?</data>',
        re.DOTALL,
    )
    TOC_BEGIN = '<div id="toc" class="toc">'
    NEWLINES = re.compile(r"\n+")
    IMG_SRC = re.compile(r'<img .*? src="(.*?)"')
    HEADERS = {
        # "user-agent": "Red-DiscordBot/" + redbot_version
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "TE": "Trailers",
    }
    WIKI_URL = "https://wiki.ss13.co"
    API_URL = WIKI_URL + "/api.php"

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    def similarity(self, title, query):
        title = "".join(filter(str.isalnum, title.lower()))
        query = "".join(filter(str.isalnum, query.lower()))
        result = 1 - Levenshtein.distance(title, query) / max(len(title), len(query))
        if query in title:
            result += 2
        return result

    def fix_fragment_urls(self, text):
        text = text.replace(" ", "_")

        def char_replace(c):
            if c.isalnum() or c in "_-":
                return c
            else:
                return "." + hex(ord(c))[2:].upper()

        text = "".join(char_replace(c) for c in text)
        return text

    @commands.command(aliases=["wiki13", "w13"])
    async def wikiss13(self, ctx: commands.Context, *, query: str):
        """Get information from Goonstation Wiki."""
        async with ctx.typing():
            payload = self.generate_payload(query)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.API_URL, params=payload, headers=self.HEADERS
                ) as res:
                    result = await res.json(content_type=None)

                embed_tasks = []
                if "query" in result and "pages" in result["query"]:
                    result["query"]["pages"].sort(
                        key=lambda unsorted_page: unsorted_page["index"]
                    )
                    pages = result["query"]["pages"]
                    if "redirects" in result["query"]:
                        for redirect in result["query"]["redirects"]:
                            skip = False
                            for page in pages:
                                if (
                                    page["title"] == redirect["to"]
                                    and not "tofragment" in redirect
                                ):
                                    skip = True
                                    break
                            if skip:
                                continue
                            page = {
                                "title": redirect["from"],
                                "fullurl": self.WIKI_URL
                                + "/"
                                + self.fix_fragment_urls(redirect["to"]),
                                "redirect_title": redirect["to"],
                            }
                            if "tofragment" in redirect:
                                page["fullurl"] += "#" + self.fix_fragment_urls(
                                    redirect["tofragment"]
                                )
                                page["tofragment"] = self.fix_fragment_urls(
                                    redirect["tofragment"]
                                )
                            pages.append(page)
                    pages.sort(key=lambda page: -self.similarity(page["title"], query))
                    for page in pages:
                        if (
                            "categories" in page
                            and page["categories"]
                            and "title" in page["categories"][0]
                            and page["categories"][0]["title"]
                            == self.DISAMBIGUATION_CAT
                        ):
                            continue  # Skip disambiguation pages
                        if not ctx.channel.permissions_for(ctx.me).embed_links:
                            # No embeds here :(
                            await ctx.send(
                                warning(
                                    f"I'm not allowed to do embeds here, so here's the first result:\n{page['fullurl']}"
                                )
                            )
                            return
                        embed_tasks.append(self.generate_embed(page, session))
                        if not ctx.channel.permissions_for(ctx.me).add_reactions:
                            break  # Menu can't function so only show first result
                embeds = await asyncio.gather(*embed_tasks, return_exceptions=True)

        if not embeds:
            await ctx.send(
                error(f"I'm sorry, I couldn't find \"{query}\" on SS13 Wiki")
            )
        elif len(embeds) == 1:
            embeds[0].set_author(name=f"Result 1 of 1")
            await ctx.send(embed=embeds[0])
        else:
            count = 0
            for embed in embeds:
                count += 1
                embed.set_author(name=f"Result {count} of {len(embeds)}")
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    def generate_payload(self, query: str):
        """Generate the payload for Goonstation Wiki based on a query string."""
        query_tokens = query.split()
        payload = {
            # Main module
            "action": "query",  # Fetch data from and about MediaWiki
            "format": "json",  # Output data in JSON format
            # format:json options
            "formatversion": "2",  # Modern format
            # action:query options
            "generator": "search",  # Get list of pages by executing a query module
            "redirects": "1",  # Automatically resolve redirects
            "prop": "info|revisions|categories",  # Which properties to get
            # action:query/generator:search options
            "gsrsearch": " ".join(query_tokens),  # Search for page titles
            # action:query/prop:info options
            "inprop": "url",  # Gives a full URL for each page
            # action:query/prop:revisions options
            "rvprop": "timestamp",  # Return timestamp of last revision
            # action:query/prop:revisions options
            "clcategories": self.DISAMBIGUATION_CAT,  # Only list this category
        }
        return payload

    async def generate_embed(self, page_json, session):
        """Generate the embed for the json page."""
        title = page_json["title"]

        page_text = None
        async with session.get(
            self.API_URL,
            params={
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "text",
                "redirects": "1",
                "formatversion": "2",
            },
            headers=self.HEADERS,
        ) as res:
            result = await res.json(content_type=None)
            page_text = html.unescape(result["parse"]["text"])

            if "tofragment" in page_json:
                fragment_match = re.search(
                    r'id="' + page_json["tofragment"] + r'".*?>', page_text
                )
                if fragment_match:
                    page_text = page_text[fragment_match.end() :]
                else:
                    tab_matches = re.findall(
                        r'<label class="tabs-label" for="tabs-input-[0-9]*-[0-9]*" data-tabpos="([0-9]*)">(.*?)</label>',
                        page_text,
                    )
                    tab_id = None
                    for tabpos, label in tab_matches:
                        if self.fix_fragment_urls(label) == page_json["tofragment"]:
                            tab_id = int(tabpos)
                            break
                    if tab_id is not None:
                        page_text = page_text.split(
                            f'class="tabs-content tabs-content-{tab_id}">'
                        )[1]
                    else:
                        page_text = "ERROR"
            page_text = re.sub(self.IGNORE_STUFF, "", page_text)

        url = page_json["fullurl"]

        def format_desc(text):
            text = re.sub(self.TOC, "", text)
            text = re.sub(r"<br />", "\n", text)
            text = re.sub(r"<br.*?>", "\n", text)
            text = re.sub(r"<li.*?>", "● ", text)
            text = re.sub(r"<i.*?>(.*?)</i>", r"*\1*", text)
            text = re.sub(r"<b.*?>(.*?)</b>", r"**\1**", text)
            text = re.sub(r"<h[12345].*?>(.*?)</h[12345]>", r"**\1**", text)
            text = re.sub(r"<div class=\"tabs-label\" tabindex=\"-1\">(?:.*?)ecret(?:.*?)</div><menu class=\"tabs-content\" style=\"\">(.*?)</menu></div>", r"||\1||", text)
            text = re.sub(
                r'<a[^>]*?href="(/.*?)"[^>]*?>(.*?)</a>',
                r"[\2](https://wiki.ss13.co\1)",
                text,
            )
            text = re.sub(
                r'<a[^>]*?href="(#.*?)"[^>]*?>(.*?)</a>',
                r"[\2](" + url.split("#")[0] + r"\1)",
                text,
            )
            text = re.sub(self.HTML_TAG, "", text)
            text = text.replace("____", "")
            text = re.sub(r"\[_?_?edit_?_?\]", "", text).strip()
            return text

        description = page_text

        is_log = len(description) / (1 + len(re.findall(r"<p>", description))) < 150

        found_toc = False
        if self.TOC_BEGIN in description:
            found_toc = True
            description = description.split(self.TOC_BEGIN)[0]

        description = format_desc(description)
        if not found_toc and len(description) > 1600 and not is_log:
            description = ""
        if len(description) < 60:
            matches = re.finditer(r"^((.|\n)*?)</tr>", page_text)
            matches = chain(matches, re.finditer(r"^((.|\n)*?)<p>", page_text))
            matches = chain(matches, re.finditer(r"<p>((.|\n)*?)</p>", page_text))
            for match in matches:
                description = match.group(1)
                description = format_desc(description)
                if len(description) >= 60:
                    break

        description = re.sub(r"\s*(\n|\r)\s*", "\n", description)

        image = (
            page_json["original"]["source"]
            if "original" in page_json and "source" in page_json["original"]
            else None
        )
        if image is None:
            match = re.search(self.IMG_SRC, page_text)
            if match:
                image = self.WIKI_URL + match.group(1)
        timestamp = (
            isoparse(page_json["revisions"][0]["timestamp"])
            if "revisions" in page_json
            and page_json["revisions"]
            and "timestamp" in page_json["revisions"][0]
            else None
        )

        whitespace_location = None
        whitespace_check_result = self.WHITESPACE.search(description)
        if whitespace_check_result:
            whitespace_location = whitespace_check_result.start()
        if whitespace_location:
            description = description[:whitespace_location].strip()
        if sum(c == "\n" for c in description) < 8:
            description = self.NEWLINES.sub("\n\n", description)
        if len(description) > 1000 or whitespace_location:
            description = description[:1000].strip()
            description += f"... [(read more)]({url})"

        if "redirect_title" in page_json:
            title = title + " → " + page_json["redirect_title"]

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Colour.from_rgb(223, 191, 49),
            url=url,
            timestamp=timestamp or None,
        )
        if image:
            embed.set_image(url=image)
        text = "Information provided by Goonstation"
        if timestamp:
            text += f"\nArticle last updated"
        embed.set_footer(
            text=text,
            icon_url=("https://wiki.ss13.co/favicon.ico"),
        )
        return embed
