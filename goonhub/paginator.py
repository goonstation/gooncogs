import discord
import datetime
from redbot.core.utils.chat_formatting import pagify
from .request import GoonhubRequest
from .utilities import timestampify
import logging

class PaginatorView(discord.ui.View):
    def __init__(self, Goonhub, author, path, params={}, embed_config={}):
        super().__init__(timeout = 90)
        self.Goonhub = Goonhub
        self.user = author
        self.path = path
        self.params = {
            'per_page': 10
        } | params
        self.embed_config = {
            'title': '',
            'color': discord.Color.from_str("#ff2222"),
            'url': '',
            'description': ''
        } | embed_config
        
        self.final_page = 1
        self.fields = list()
        self.embeds = list()
        self.cont = ""
        self.current_page = 0
        self.fin = False
        self.embed_idx = 0
        self.message = None
        
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_idx > 0:
            self.embed_idx -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.embed_idx], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed_idx < len(self.embeds) - 1:
            await interaction.response.defer()
            self.embed_idx += 1
        elif not self.fin:
            try:
                await interaction.response.defer(thinking=True)
                self.embeds.append(await self.build_page())
                followup = await interaction.followup.send("goodbye", wait=True)
                await followup.delete()
            except Exception as e:
                await interaction.followup.send(f"{e}")
                self.stop()
                await interaction.message.edit(view=None)
                return
            self.embed_idx += 1
        self.update_buttons()
        await interaction.message.edit(embed=self.embeds[self.embed_idx], view=self)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.red)
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.message.delete()
        
    def update_buttons(self):
        self.children[0].disabled = self.embed_idx == 0
        self.children[1].disabled = self.fin and self.embed_idx == len(self.embeds) - 1

    async def on_timeout(self) -> None:
        await self.message.edit(view=None)

    async def interaction_check(self, interaction: discord.Interaction[discord.Client]) -> bool:
        return interaction.user == self.user
    
    async def fetch_first_page(self) -> discord.Embed:
        embed = await self.build_page()
        self.embeds.append(embed)
        self.update_buttons()
        return embed
    
    async def build_page(self) -> discord.Embed:
        curr_size = len(self.embed_config["title"])
        curr_size += len(self.embed_config["description"])

        embed = discord.Embed(
            title = self.embed_config["title"],
            color = self.embed_config["color"],
            url = self.embed_config["url"],
            description = self.embed_config["description"]
        )
        pagenames = list()

        def add_field(field_data):
            nonlocal embed, curr_size
            curr_size += field_data[0]
            embed.add_field(name = field_data[1], value = field_data[2], inline = False)

        while len(embed.fields) < 10: #loop until 10 fields - can also break if charlimit is reached
            if len(self.fields) == 0: #if we are out of fields to append, fetch another batch
                if self.current_page == self.final_page: #if we are out of pages to fetch, also break
                    break
                else:
                    await self.extract_fields(await self.fetch_page(self.current_page + 1))

            if curr_size + self.fields[0][0] > 5900: #if next field would put us over, finish adding fields
                break
            add_field(self.fields.pop(0))
            pagenames.append(f"{self.current_page}{self.cont}")

        embed.set_footer(text = f"Page {pagenames[0]}{f' - {pagenames[-1]}'  if pagenames[0]!=pagenames[-1] else ''} of {self.final_page}")
        self.cont = " (cont)" #for next embed, mark as continuing previous page
        if len(self.fields) == 0 and self.current_page == self.final_page:
            self.fin = 1
        return embed
    
    async def build_field(self, item, timestamps) -> dict:
        pass
    
    async def extract_fields(self, data):
        self.final_page = data["meta"]["last_page"] #fetching a new page, update our metas and mark as starting a new page
        self.current_page = data["meta"]["current_page"]
        self.cont = ""
        if int(data["meta"]["total"]) == 0:
            raise Exception(f"No results found")
        for item in data["data"]:
            timestamps = { 'created_at': None, 'updated_at': None }
            if item["created_at"]:
                timestamps["created_at"] = timestampify(item["created_at"])
            if item["updated_at"]:
                timestamps["updated_at"] = timestampify(item["updated_at"])
                
            field = await self.build_field(item, timestamps)
            field_name = field["name"]
            field_text = field["text"]
            
            for i, field_value in enumerate(pagify(field_text, delims=('\n', ' '), priority=True, page_length=1024)):
                _field_name = field_name
                if i == 1:
                    _field_name = "..."
                elif i > 1:
                    _field_name = f"... ({i})"
                field_size = len(_field_name) + len(field_value)
                self.fields.append((field_size, _field_name, field_value))
        
    async def fetch_page(self, page) -> dict:
        req = await GoonhubRequest(self.Goonhub.bot, self.Goonhub.session)
        params = self.params | { 'page': page }
        return await req.get(self.path, params = params)
