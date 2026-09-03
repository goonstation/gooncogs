from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red


@dataclass(frozen=True)
class PointType:
    name: str
    emoji: Optional[str] = None
    plural: Optional[str] = None
    check_command: Optional[str] = None
    give_command: Optional[str] = None
    cannot_give_message: str = "You cannot give {0}."
    given_message_num: str = "{0} now owns {1} {2}."
    given_message_emoji: str = "{0} now owns {1}."
    allow_command: Optional[str] = None
    allow_successful_message: str = "{0} can now give {1}."
    allow_cant_message: str = "You can't give {0} so you also can't let others do that."
    allow_already_giver_message: str = "{0} can already give {1}."
    no_points_message: str = "{0} owns no {1}."
    has_points_message_num: str = "{0} owns {1} {2}."
    has_points_message_emoji: str = "{0} owns {1}."

    @property
    def plural_name(self) -> str:
        return self.plural or f"{self.name}s"


def make_check_command(point_type: PointType):
    command_name = point_type.check_command or point_type.plural_name

    async def callback(
        self,
        ctx: commands.Context,
        user: discord.User = None,
    ):
        await self.check_points(ctx, point_type, user)

    callback.__name__ = f"check_{point_type.name}_points"
    return commands.command(
        name=command_name,
        help=f"Check how many {point_type.plural_name} someone has.",
    )(callback)


def make_give_command(point_type: PointType):
    command_name = point_type.give_command or f"give{point_type.name}"

    async def callback(
        self,
        ctx: commands.Context,
        user: discord.User,
    ):
        await self.give_points(ctx, point_type, user)

    callback.__name__ = f"give_{point_type.name}_points"
    return commands.command(
        name=command_name,
        help=f"Give someone a {point_type.name} if you can.",
    )(callback)


def make_allow_command(point_type: PointType):
    if point_type.allow_command is None:
        raise ValueError(f"No allow command configured for {point_type.name}.")

    async def callback(
        self,
        ctx: commands.Context,
        user: discord.User,
    ):
        await self.allow_give_points(ctx, point_type, user)

    callback.__name__ = f"allow_giving_{point_type.name}_points"
    return commands.command(
        name=point_type.allow_command,
        help=f"Let someone give {point_type.plural_name} if you can.",
    )(callback)


class PointCogMeta(commands.CogMeta):
    def __new__(mcls, name, bases, attrs, **kwargs):
        command_names = set()
        for point_type in attrs.get("point_types", ()):
            point_commands = [
                make_check_command(point_type),
                make_give_command(point_type),
            ]
            if point_type.allow_command is not None:
                point_commands.append(make_allow_command(point_type))

            for command in point_commands:
                if command.name in command_names:
                    raise TypeError(f"Duplicate generated command name: {command.name}")
                command_names.add(command.name)
                attrs[command.callback.__name__] = command

        return super().__new__(mcls, name, bases, attrs, **kwargs)


class GivePoints(commands.Cog, metaclass=PointCogMeta):
    point_types = (
        PointType(
            name="rat",
            emoji="\N{RAT}",
            give_command="giverats",
            cannot_give_message="You can't give people rats, you don't work at the rats factory.",
            allow_command="hireratsfactoryworker",
            allow_cant_message="You can't hire people as rats factory workers, you don't work at the rats factory.",
            allow_already_giver_message="{0} already works in the rats factory.",
            allow_successful_message="{0} has been hired as a rats factory worker.",
        ),
        PointType(
            name="cat",
            emoji="\N{CAT}",
            give_command="givecats",
            cannot_give_message="You can't give people cats, you don't work at the cats factory.",
            allow_command="hirecatsfactoryworker",
            allow_cant_message="You can't hire people as cats factory workers, you don't work at the cats factory.",
            allow_already_giver_message="{0} already works in the cats factory.",
            allow_successful_message="{0} has been hired as a cats factory worker.",
        ),
        PointType(
            name="bat",
            emoji="<:dracula:710538131614466058>",
            give_command="givebats",
            cannot_give_message="You can't give people bats, you don't work at the bats factory.",
            allow_command="hirebatsfactoryworker",
            allow_cant_message="You can't hire people as bats factory workers, you don't work at the bats factory.",
            allow_already_giver_message="{0} already works in the bats factory.",
            allow_successful_message="{0} has been hired as a bats factory worker.",
        ),
        PointType(
            name="bouncerat",
            emoji="<a:bouncerat:604890193291378698>",
            give_command="givebouncerats",
            cannot_give_message="You can't give people bouncerats, you don't work at the bouncerats factory.",
            allow_command="hirebounceratsfactoryworker",
            allow_cant_message="You can't hire people as bouncerats factory workers, you don't work at the bouncerats factory.",
            allow_already_giver_message="{0} already works in the bouncerats factory.",
            allow_successful_message="{0} has been hired as a bouncerats factory worker.",
        ),
        PointType(
            name="bee",
            emoji="\N{HONEYBEE}",
            allow_command="hirebeefactoryworker",
        ),
        PointType(
            name="what",
            emoji="<:what:875269167383740436>",
            give_command="givewhat",
            cannot_give_message="You can't give people whats, you don't work at the what factory.",
            allow_command="hirewhatfactoryworker",
            allow_cant_message="You can't hire people as what factory workers, you don't work at the what factory.",
            allow_already_giver_message="{0} already works in the what factory.",
            allow_successful_message="{0} has been hired as a what factory worker.",
        ),
    )

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=659401743619236)
        self.config.register_user(points={}, can_give_points={})

    async def check_points(
        self,
        ctx: commands.Context,
        point_type: PointType,
        user: Optional[discord.User],
    ):
        user = user or ctx.author
        user_points = await self.config.user(user).points()
        points = user_points.get(point_type.name, 0)
        if points == 0:
            await ctx.send(
                point_type.no_points_message.format(user.name, point_type.plural_name)
            )
        elif point_type.emoji is None:
            await ctx.send(
                point_type.has_points_message_num.format(
                    user.name, points, point_type.plural_name
                )
            )
        else:
            await ctx.send(
                point_type.has_points_message_emoji.format(
                    user.name, point_type.emoji * points
                )
            )

    async def give_points(
        self,
        ctx: commands.Context,
        point_type: PointType,
        user: discord.User,
    ):
        author_can_give = (
            await self.config.user(ctx.author).can_give_points()
        ).get(point_type.name, False)
        if not author_can_give:
            await ctx.send(
                point_type.cannot_give_message.format(
                    point_type.name, ctx.author.name
                )
            )
            return

        async with self.config.user(user).points() as points:
            points[point_type.name] = points.get(point_type.name, 0) + 1
            new_total = points[point_type.name]

        if point_type.emoji is None:
            await ctx.send(
                point_type.given_message_num.format(
                    user.name,
                    new_total,
                    point_type.plural_name,
                    ctx.author.name,
                )
            )
        else:
            await ctx.send(
                point_type.given_message_emoji.format(
                    user.name, point_type.emoji * new_total, ctx.author
                )
            )

    async def allow_give_points(
        self,
        ctx: commands.Context,
        point_type: PointType,
        user: discord.User,
    ):
        author_can_give = (
            await self.config.user(ctx.author).can_give_points()
        ).get(point_type.name, False)
        if await self.bot.is_owner(ctx.author):
            author_can_give = True
        if not author_can_give:
            await ctx.send(
                point_type.allow_cant_message.format(
                    point_type.name, ctx.author.name
                )
            )
            return

        async with self.config.user(user).can_give_points() as can_give_points:
            if can_give_points.get(point_type.name, False):
                await ctx.send(
                    point_type.allow_already_giver_message.format(
                        user.name, point_type.name
                    )
                )
                return
            can_give_points[point_type.name] = True

        await ctx.send(
            point_type.allow_successful_message.format(
                user.name, point_type.name, ctx.author.name
            )
        )

    @commands.command()
    async def ratsleaderboard(self, ctx: commands.Context):
        await ctx.send("Rats are not a contest.")
