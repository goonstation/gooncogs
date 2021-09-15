import asyncio
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *

class PinOrder(commands.Cog):
    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 56317515632557985)
        self.config.register_channel(pins={})
        self.refreshes = set()

    async def refresh_pins(self, channel: discord.TextChannel):
        if channel in self.refreshes:
            return
        self.refreshes.add(channel)
        try:
            current_pins = [message.id for message in await channel.pins()]
            pin_order = list((await self.config.channel(channel).pins()).items())
            pin_order.sort()
            last_wrong_index = None
            for index, pair in reversed(list(enumerate(pin_order))):
                position, message_id = pair
                try:
                    current_index = current_pins.index(message_id)
                except ValueError:
                    current_index = -1
                if current_index != index:
                    last_wrong_index = index
                    break
            if last_wrong_index is None:
                return
            for position, message_id in reversed(pin_order[:last_wrong_index + 1]):
                try:
                    message = await channel.fetch_message(message_id)
                except discord.NotFound:
                    async with self.config.channel(channel).pins() as pins:
                        del pins[position]
                    continue
                await message.unpin(reason="Reordering pins to move them to top.")
                await message.pin(reason="Reordering pins to move them to top.")
        finally:
            self.refreshes.remove(channel)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        try:
            if not payload.data['pinned']:
                return
            channel = self.bot.get_channel(payload.channel_id)
            pins = await self.config.channel(channel).pins()
            if not pins:
                return
            await self.refresh_pins(channel)
        except:
            import traceback
            return await self.bot.send_to_owners(traceback.format_exc())

    @commands.group()
    @checks.has_permissions(manage_messages=True)
    async def pinorder(self, ctx: commands.Context):
        """Group of commands to set some messages to be always pinned on top in a specified order."""

    @pinorder.command()
    @commands.has_permissions(manage_messages=True)
    async def pin(self, ctx: commands.Context, message: discord.Message, position: int):
        """Pins a message and sets its position in the messages managed by this cog.
        Any manual pins will trigger a reshuffle of pins to keep these messages on top in the given order."""
        async with self.config.channel(ctx.channel).pins() as pins:
            if position in pins:
                conflict = ctx.channel.get_partial_message(pins[position])
                return await ctx.send(f"Message {conflict.jump_url} is already pinned on this position.\nUse the `pinorder unpin` command to remove it first.")
            pins[position] = message.id
            await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await self.refresh_pins(ctx.channel)

    @pinorder.command()
    @commands.has_permissions(manage_messages=True)
    async def refresh(self, ctx: commands.Context):
        """Manually triggers a reshuffle of pins to keep the set order."""
        await self.refresh_pins(ctx.channel)
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

    @pinorder.command()
    @commands.has_permissions(manage_messages=True)
    async def list(self, ctx: commands.Context):
        """Lists message pins managed by this cog in this channel."""
        pin_order = list((await self.config.channel(ctx.channel).pins()).items())
        pin_order.sort()
        if not pin_order:
            return await ctx.send("No pin order set in this channel.")
        lines = [f"**{position}** {ctx.channel.get_partial_message(message_id).jump_url}" for position, message_id in pin_order]
        await ctx.send('\n'.join(lines))

    @pinorder.command()
    @commands.has_permissions(manage_messages=True)
    async def unpin(self, ctx: commands.Context, message: discord.Message):
        """Unpins a message and removes it from the message pins managed by this cog."""
        if not message.pinned:
            return await ctx.send(f"This message is not pinned.")
        async with self.config.channel(ctx.channel).pins() as pins:
            for position, pinned in pins.items():
                if pinned == message.id:
                    del pins[position]
                    await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
                    break
            else:
                return await ctx.send(f"This message does not have a pin position set.")
        await message.unpin(reason="Unpinned via the PinOrder cog.")

