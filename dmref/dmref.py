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
from html.parser import HTMLParser
from collections import OrderedDict

BYOND_REF_URL = "http://www.byond.com/docs/ref/info.html"

class DMRefEntry:
	def __init__(self):
		self.title = None
		self.lists = OrderedDict()
		self.wip_body = []
		self.body = ""
		self.path = None
	
	def __str__(self):
		out = [self.title]
		for name, lines in self.lists.items():
			out.append(name)
			for value, url in lines:
				if url:
					out.append(f"	[{value}]({BYOND_REF_URL}{url})")
				else:
					out.append(f"	{value}")
		out.append(self.body)
		return '\n'.join(out)
	
	def add_to_list(self, list_name, value, url=None):
		if list_name not in self.lists:
			self.lists[list_name] = []
		self.lists[list_name].append((value, url))

	def __repr__(self):
		return f"<DMRefEntry title={repr(self.title)} see_also={repr(self.lists)} body={repr(self.body)}>"
	
	def finalize(self):
		self.body = ''.join(self.wip_body)
		self.body = self.body.replace('  ', ' ')

class DMRefParser(HTMLParser):
	def __init__(self, *, convert_charrefs: bool = ...) -> None:
		super().__init__(convert_charrefs=convert_charrefs)
		self.processing_path = None
		self.processing_entry = None
		self.processed = {}
		self.state_stack = ['init']
		self.current_list = None
		self.current_list_item_url = None
		self.current_list_item_value = None
	
	@property
	def state(self):
		return self.state_stack[-1]
	
	def push_state(self, state):
		self.state_stack.append(state)
	
	def pop_state(self, what=None):
		popped = self.state_stack.pop()
		if what is not None:
			assert popped == what
		if popped == 'dd':
			if self.current_list_item_value:
				self.processing_entry.add_to_list(self.current_list, self.current_list_item_value.strip(), self.current_list_item_url)
		return popped
	
	def pop_state_soft(self, what):
		if self.state == what:
			return self.pop_state()
	
	def add_body(self, text):
		if self.processing_entry:
			wip_body = self.processing_entry.wip_body
			if text.startswith("\n") and len(wip_body) > 0 and wip_body[-1].endswith("\n"):
				text = text.lstrip("\n")
			if text.startswith(" ") and len(wip_body) > 0 and (wip_body[-1].endswith(" ") or wip_body[-1].endswith("\n")):
				text = text.lstrip(" ")
			if not text:
				return
			self.processing_entry.wip_body.append(text)
	
	def flush_current(self):
		if self.processing_path is not None:
			self.processing_entry.finalize()
			self.processed[self.processing_path] = self.processing_entry
			self.processing_path = None
		self.processing_entry = DMRefEntry()
	
	def handle_entry_start_stop(self, tag):
		if self.state != 'entry':
			return
		if tag == 'code':
			self.add_body('`')
		elif tag == 'b':
			self.add_body('**')
		elif tag == 'i':
			self.add_body('*')

	def handle_starttag(self, tag, attrs):
		attrs = dict(attrs)
		if tag == 'a' and 'name' in attrs:
			self.flush_current()
			self.processing_path = attrs['name']
			self.processing_entry.path = self.processing_path
			self.push_state('entry')
		elif tag == 'h2' and self.state == 'entry':
			self.push_state('title')
		elif tag in ['pre', 'xmp']:
			self.push_state('codeblock')
			self.add_body('\n```c\n')
		elif tag == 'dl' and self.state == 'entry':
			self.push_state('list')
			self.current_list = ""
		elif tag == 'dt' and self.state == 'list':
			self.pop_state_soft('dd')
			self.pop_state_soft('dt')
			self.push_state('dt')
		elif tag == 'dd' and self.state in ['list', 'dt', 'dd']:
			self.pop_state_soft('dd')
			self.pop_state_soft('dt')
			self.push_state('dd')
			self.current_list_item_value = ""
			self.current_list_item_url = None
		elif tag == 'a' and self.state == 'dd':
			self.current_list_item_url = attrs['href']
		elif tag == 'h3' and self.state == 'entry':
			self.push_state('subtitle')
		elif tag == 'p' and self.state == 'entry':
			self.add_body('\n')
		
		self.handle_entry_start_stop(tag)

	def handle_endtag(self, tag):
		if tag == 'h2':
			self.pop_state_soft('title')
		elif tag in ['pre', 'xmp']:
			self.pop_state('codeblock')
			self.add_body('\n```\n')
		elif tag == 'dl' and self.state in ['list', 'dd', 'dt']:
			self.pop_state_soft('dd')
			self.pop_state_soft('dt')
			self.pop_state('list')
			self.current_list = None
		elif tag == 'h3':
			self.pop_state_soft('subtitle')

		self.handle_entry_start_stop(tag)

	def handle_data(self, data):
		if not data.strip():
			return
		if self.state == 'title':
			self.processing_entry.title = data
		if self.state == 'subtitle':
			self.add_body(f"\n**{data.strip()}**\n")
		elif self.state == 'entry':
			self.add_body(data.replace('\n', ' '))
		elif self.state == 'codeblock':
			self.add_body(data)
		elif self.state == 'dt':
			if self.current_list == "":
				self.current_list = data.strip()
		elif self.state == 'dd':
			self.current_list_item_value += data


class DMRef(commands.Cog):
	def __init__(self, bot: Red):
		self.bot = bot
		self.session = aiohttp.ClientSession()

	async def init(self):
		parser = DMRefParser()
		async with self.session.get(BYOND_REF_URL) as res:
			if res.status != 200:
				return res
			parser.feed(await res.text())
		self.entries = parser.processed

	def cog_unload(self):
		asyncio.create_task(self.session.cancel())

	def ckeyify(self, text):
		return ''.join(c.lower() for c in text if c.isalnum())

	def find_entries(self, search):
		search = search.lower().strip()
		csearch = self.ckeyify(search)
		search_words = [self.ckeyify(w) for w in search.split()]
		result_tiers = [[] for x in range(6)]
		for key, value in self.entries.items():
			if search == key.split('/')[-1]:
				result_tiers[0].append(value)
			elif search in key.split('/'):
				result_tiers[1].append(value)
			elif search in key:
				result_tiers[2].append(value)
			elif search in value.title:
				result_tiers[3].append(value)
			elif csearch in self.ckeyify(value.title) or csearch in self.ckeyify(key):
				result_tiers[4].append(value)
			elif all(w in value.title or w in key for w in search_words):
				result_tiers[5].append(value)
		#return next(results for results in result_tiers if results)
		return sum(result_tiers, [])

	def process_entry_list(self, entry, name, separator=' - ', sep_on_first=True):
		if not name in entry.lists:
			return []
		lines = entry.lists[name]
		if not lines:
			return []
		output = []
		output.append(f"__{name}__ ")
		first = True
		for value, url in lines:
			if name == 'Format:':
				value = f"`{value}`"
			elif name == 'Args:':
			    if ':' in value:
				    argname, rest = value.split(':', maxsplit=1)
				    value = f"`{argname}`: " + rest
			line = None
			if url:
				line = f"[{value}]({BYOND_REF_URL}{url})"
			else:
				line = value
			if len(lines) == 1:
				output[-1] += " " + line
			elif first and not sep_on_first:
				output.append(line)
			else:
				output.append(separator + line)
			first = False
		return output

	@commands.command()
	async def dmref(self, ctx: commands.Context, *, search: str):
		"""Searches the DM language reference and displays results neatly."""
		entries = self.find_entries(search)
		if not entries:
			await ctx.send("No results found.")
			return
		embed_colour = await ctx.embed_colour()
		pages = []
		for entry in entries:
			desc = []
			for name in entry.lists:
				if name in ['See also:']:
					continue
				desc += self.process_entry_list(entry, name)
			desc.append(entry.body)
			desc.append(''.join(self.process_entry_list(entry, 'See also:', ' | ', False)))
			desc = '\n'.join(desc)
			desc_parts = list(pagify(desc, page_length=4000))
			for i, desc_part in enumerate(desc_parts):
				title = entry.title
				page_part_text = f" ({i + 1}/{len(desc_parts)})" if len(desc_parts) > 1 else ""
				title += page_part_text
				current_embed = discord.Embed(
						title = title,
						color = embed_colour,
						description = desc_part,
						url = f"{BYOND_REF_URL}#{entry.path}",
					)
				current_embed.set_footer(text=entry.path + page_part_text)
				pages.append(current_embed)

		for i, page in enumerate(pages):
			page.set_footer(text=f"{i+1}/{len(pages)} | {page.footer.text}")
		if not pages:
			await ctx.send("Something went wrong")
			return
		if len(pages) > 1:
			await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60.0)
		else:
			await ctx.send(embed=pages[0])
