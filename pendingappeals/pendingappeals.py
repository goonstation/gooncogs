import asyncio
import aiohttp
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import logging
import datetime
from bs4 import BeautifulSoup
import itertools
from redbot.core.utils.chat_formatting import pagify
import re

BASE_URL = "https://forum.ss13.co/"


class PendingAppeals(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 95222448842)
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        asyncio.create_task(self.session.close())

    def parse_post_key(self, text):
        return re.search(r'var my_post_key = "([0-9a-f]*)";', text).groups()[0]

    async def get_post_key(self):
        tokens = (await self.bot.get_shared_api_tokens("mybb"))
        async with self.session.get(tokens.get('url')) as res:
            return self.parse_post_key(await res.text())

    async def login(self):
        tokens = (await self.bot.get_shared_api_tokens("mybb"))
        login_data = {
            "action": "do_login",
            "url": tokens.get('url') + "member.php",
            "quick_login": "1",
            "my_post_key": await self.get_post_key(),
            "quick_username": tokens.get('username'),
            "quick_password": tokens.get('password'),
            "quick_remember": "yes",
            "submit": "Login"
        }
        async with self.session.post(login_data['url'], data=login_data) as res:
            return res.status == 200

    async def test_thread(self, elem, labels_only=True):
        waiting_for_player_response = False
        try:
            if "forumdisplay_sticky" in elem.find_parent("td").get_attribute_list(
                "class"
            ):
                return None
            if "label" in elem.previousSibling.previousSibling.get_attribute_list(
                "class"
            ):
                label_elem = elem.previousSibling.previousSibling
                if label_elem.text.strip() == "Waiting For Player Response":
                    waiting_for_player_response = True
                else:
                    return None
        except:
            pass
        tokens = await self.bot.get_shared_api_tokens("mybb")
        if elem.a is None:
            return None
        url = tokens.get('url') + elem.a.get_attribute_list("href")[0]
        if not labels_only or waiting_for_player_response:
            async with self.session.get(url) as res:
                bs = BeautifulSoup(await res.text(), "html")
                admin_replied = False
                last_is_player = True
                for auth_info in bs.find_all(class_="author_information"):
                    try:
                        rank = auth_info.find(class_="smalltext").text.strip().lower()
                        if "admin" in rank or "developer" in rank:
                            admin_replied = True
                            last_is_player = False
                        else:
                            last_is_player = True
                    except:
                        pass
                if waiting_for_player_response and not last_is_player:
                    return None
                elif not waiting_for_player_response and not labels_only and admin_replied:
                    return None
        return f"<{url}> {elem.a.text}"

    async def scrape_page(self, page, forum_id, labels_only=True):
        result = []
        tokens = await self.bot.get_shared_api_tokens("mybb")
        async with self.session.get(
            tokens.get('url') + f"forumdisplay.php?fid={forum_id}&page={page}"
        ) as res:
            bs = BeautifulSoup(await res.text())
            elems = bs.find_all(class_="subject_new") + bs.find_all(class_="subject_old")
            result = await asyncio.gather(
                *[self.test_thread(elem, labels_only) for elem in elems]
            )
        return [x for x in result if x is not None]

    @commands.command()
    @checks.admin()
    async def pendingappeals(
        self, ctx: commands.Context, pages: int = 4, check_only_labels: bool = True
    ):
        """Scrapes the Goonstation forum for unresponded to appeals."""
        await self.login()
        results = await asyncio.gather(
            *(
                [
                    self.scrape_page(page, forum_id=54, labels_only=check_only_labels)
                    for page in range(1, pages + 1)
                ]
                + [
                    self.scrape_page(page, forum_id=4, labels_only=check_only_labels)
                    for page in range(1, pages + 1)
                ]
                + [
                    self.scrape_page(page, forum_id=35, labels_only=False)
                    for page in range(1, pages + 1)
                ]
            )
        )
        result = itertools.chain(*results)
        result = list(dict.fromkeys(result)) # remove duplicates caused by not enough pages
        if not result:
            await ctx.send("No pending appeals found")
        else:
            for page in pagify("\n".join(result)):
                await ctx.send(page)
