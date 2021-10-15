import asyncio
import discord
from github import Github
from redbot.core import commands, Config, checks
from redbot.core.bot import Red

class GivePoints(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=659401743619236)
        self.config.register_user(points={}, can_give_points={})

    @commands.command()
    async def ratsleaderboard(self, ctx: commands.Context):
        await ctx.send("Rats are not a contest.")

def add_points_type(cog,
        points_name,
        points_emoji = None,
        points_name_plural = None,
        points_check_command = None,
        no_points_message = "{0} owns no {1}.",
        has_points_message_num = "{0} owns {1} {2}.",
        has_points_message_emoji = "{0} owns {1}.",
        points_give_command = None,
        cannot_give_message = "You cannot give {0}.",
        given_points_message_num = "{0} now owns {1} {2}.",
        given_points_message_emoji = "{0} now owns {1}.",
        allow_give_command = None, # None = disabled here!!!
        allow_successful_message = "{0} can now give {1}.",
        allow_cant_message = "You can't give {0} so you also can't let others do that.",
        allow_already_giver_message = "{0} can already give {1}.",
        ):
    if points_name_plural is None:
        points_name_plural = points_name + "s"

    @commands.command(
            name=points_check_command or points_name_plural,
            help=f"""Check how many {points_name_plural} someone has.""")
    async def check_points(self, ctx: commands.Context, user: discord.User=None):
        if user is None:
            user = ctx.message.author
        user_points = await self.config.user(user).points()
        points = user_points.get(points_name, 0)
        if points == 0:
            await ctx.send(no_points_message.format(user.name, points_name_plural))
        elif points_emoji is None:
            await ctx.send(has_points_message_num.format(user.name, points, points_name_plural))
        else:
            await ctx.send(has_points_message_emoji.format(user.name, points_emoji * points))
    cog.__cog_commands__.append(check_points)

    @commands.command(
            name=points_give_command or "give" + points_name,
            help=f"""Give someone a {points_name} if you can.""")
    async def give_points(self, ctx: commands.Context, user: discord.User):
        author_can_give = (await self.config.user(ctx.message.author).can_give_points()).get(points_name, False)
        if not author_can_give:
            await ctx.send(cannot_give_message.format(points_name, ctx.message.author.name))
            return
        async with self.config.user(user).points() as points:
            points[points_name] = points.get(points_name, 0) + 1
        if points_emoji is None:
            await ctx.send(given_points_message_num.format(user.name, points[points_name], points_name_plural, ctx.message.author.name))
        else:
            await ctx.send(given_points_message_emoji.format(user.name, points_emoji * points[points_name], ctx.message.author))
    cog.__cog_commands__.append(give_points)

    if allow_give_command is not None:
        @commands.command(
                name=allow_give_command,
                help=f"""Let someone give {points_name_plural} if you can.""")
        async def allow_give_points(self, ctx: commands.Context, user: discord.User):
            author_can_give = (await self.config.user(ctx.message.author).can_give_points()).get(points_name, False)
            if await self.bot.is_owner(ctx.message.author):
                author_can_give = True
            if not author_can_give:
                await ctx.send(allow_cant_message.format(points_name, ctx.message.author.name))
                return
            async with self.config.user(user).can_give_points() as can_give_points:
                if can_give_points.get(points_name, False):
                    await ctx.send(allow_already_giver_message.format(user.name, points_name))
                    return
                can_give_points[points_name] = True
                await ctx.send(allow_successful_message.format(user.name, points_name, ctx.message.author.name))
        cog.__cog_commands__.append(allow_give_points)

# TODO viral, limited

add_points_type(GivePoints,
    "rat", "\N{RAT}",
    points_give_command = "giverats",
    cannot_give_message = "You can't give people rats, you don't work at the rats factory.",
    allow_give_command = "hireratsfactoryworker",
    allow_cant_message = "You can't hire people as rats factory workers, you don't work at the rats factory.",
    allow_already_giver_message = "{0} already works in the rats factory.",
    allow_successful_message = "{0} has been hired as a rats factory worker.")

add_points_type(GivePoints,
        "bat", "<:dracula:710538131614466058>",
    points_give_command = "givebats",
    cannot_give_message = "You can't give people bats, you don't work at the bats factory.",
    allow_give_command = "hirebatsfactoryworker",
    allow_cant_message = "You can't hire people as bats factory workers, you don't work at the bats factory.",
    allow_already_giver_message = "{0} already works in the bats factory.",
    allow_successful_message = "{0} has been hired as a bats factory worker.")

add_points_type(GivePoints,
    "bouncerat", "<a:bouncerat:604890193291378698>",
    points_give_command = "givebouncerats",
    cannot_give_message = "You can't give people bouncerats, you don't work at the bouncerats factory.",
    allow_give_command = "hirebounceratsfactoryworker",
    allow_cant_message = "You can't hire people as bouncerats factory workers, you don't work at the bouncerats factory.",
    allow_already_giver_message = "{0} already works in the bouncerats factory.",
    allow_successful_message = "{0} has been hired as a bouncerats factory worker.")
