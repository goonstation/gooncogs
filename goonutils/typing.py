from contextlib import asynccontextmanager, suppress

import discord
from redbot.core import commands


@asynccontextmanager
async def safe_typing(ctx: commands.Context):
    """Show a typing indicator without allowing API failures to abort commands"""
    typing = ctx.typing()
    try:
        await typing.__aenter__()
    except discord.HTTPException:
        yield
        return

    try:
        yield
    finally:
        await typing.__aexit__(None, None, None)


async def defer_or_typing(ctx: commands.Context):
    """In interactions / slash commands uses defer, otherwise uses typing"""
    if ctx.interaction:
        await ctx.defer()
    else:
        with suppress(discord.HTTPException):
            await ctx.typing()
