import discord
import typing
import random
import datetime
from itertools import accumulate
from bisect import bisect
from redbot.core import commands, app_commands
import logging

goonservers = None

EMOJI_RANGES_UNICODE = {
    6: [
        ("\U0001F300", "\U0001F320"),
        ("\U0001F330", "\U0001F335"),
        ("\U0001F337", "\U0001F37C"),
        ("\U0001F380", "\U0001F393"),
        ("\U0001F3A0", "\U0001F3C4"),
        ("\U0001F3C6", "\U0001F3CA"),
        ("\U0001F3E0", "\U0001F3F0"),
        ("\U0001F400", "\U0001F43E"),
        ("\U0001F440",),
        ("\U0001F442", "\U0001F4F7"),
        ("\U0001F4F9", "\U0001F4FC"),
        ("\U0001F500", "\U0001F53C"),
        ("\U0001F540", "\U0001F543"),
        ("\U0001F550", "\U0001F567"),
        ("\U0001F5FB", "\U0001F5FF"),
    ],
    7: [
        ("\U0001F300", "\U0001F32C"),
        ("\U0001F330", "\U0001F37D"),
        ("\U0001F380", "\U0001F3CE"),
        ("\U0001F3D4", "\U0001F3F7"),
        ("\U0001F400", "\U0001F4FE"),
        ("\U0001F500", "\U0001F54A"),
        ("\U0001F550", "\U0001F579"),
        ("\U0001F57B", "\U0001F5A3"),
        ("\U0001F5A5", "\U0001F5FF"),
    ],
    8: [
        ("\U0001F300", "\U0001F579"),
        ("\U0001F57B", "\U0001F5A3"),
        ("\U0001F5A5", "\U0001F5FF"),
    ],
}

def get_server_choices(current: str = '', with_all: bool = False):
    global goonservers
    if goonservers is None:
        import goonhub.settings as settings
        goonservers = settings.Bot.get_cog("GoonServers")
    
    choices = []            
    current = current.lower()
    if with_all:
        for category in goonservers.categories.keys():
            add_choice = False
            if not current or current and current in category.lower():
                add_choice = True
            if add_choice:
                choices.append({ 'label': category.capitalize(), 'value': category })
    
    for server in goonservers.servers:
        add_choice = False
        if current:
            for alias in server.aliases:
                if current in alias.lower():
                    add_choice = True
                    break
        else:
            add_choice = True
        if add_choice:
            choices.append({ 'label': server.short_name, 'value': server.tgs })

    return choices

async def servers_autocomplete(ctx: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = get_server_choices(current, False)
    return [app_commands.Choice(name=choice['label'], value=choice['value']) for choice in choices]

async def servers_autocomplete_all(ctx: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = get_server_choices(current, True)
    return [app_commands.Choice(name=choice['label'], value=choice['value']) for choice in choices]

async def success_response(ctx: commands.Context):
    if ctx.interaction:
        await ctx.send("\N{WHITE HEAVY CHECK MARK}")
    else:
        await ctx.message.add_reaction("\N{WHITE HEAVY CHECK MARK}")

def random_emoji(unicode_version=8, rnd=random):
    if unicode_version in EMOJI_RANGES_UNICODE:
        emoji_ranges = EMOJI_RANGES_UNICODE[unicode_version]
    else:
        emoji_ranges = EMOJI_RANGES_UNICODE[-1]

    # Weighted distribution
    count = [ord(r[-1]) - ord(r[0]) + 1 for r in emoji_ranges]
    weight_distr = list(accumulate(count))

    # Get one point in the multiple ranges
    point = rnd.randrange(weight_distr[-1])

    # Select the correct range
    emoji_range_idx = bisect(weight_distr, point)
    emoji_range = emoji_ranges[emoji_range_idx]

    # Calculate the index in the selected range
    point_in_range = point
    if emoji_range_idx != 0:
        point_in_range = point - weight_distr[emoji_range_idx - 1]

    # Emoji 😄
    emoji = chr(ord(emoji_range[0]) + point_in_range)
    emoji_codepoint = "U+{}".format(hex(ord(emoji))[2:].upper())

    return (emoji, emoji_codepoint)

def ckeyify(text: str) -> str:
    return ''.join(c.lower() for c in text if c.isalnum())

def timestampify(time: str) -> str:
    return f"<t:{int(datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp())}:f>"
