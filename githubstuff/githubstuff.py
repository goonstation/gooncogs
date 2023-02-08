import discord
from github import Github
from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import *
from github import Github
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
import requests
import random
import math


class GithubStuff(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=825749154751274)
        self.config.register_global(
            repo=None,
            branch="master",
            changelog_path=None,
            admin_changelog_path=None,
        )
        self.gh = None

    async def cog_before_invoke(self, ctx: commands.Context):
        if self.gh is None:
            self.gh = Github(
                (await self.bot.get_shared_api_tokens("github")).get("token")
            )
        return await super().cog_before_invoke(ctx)

    @commands.group(aliases=["gh"])
    async def github(self, ctx: commands.Context):
        """Group command for github stuff"""
        pass

    @github.command(name="set_changelog")
    @commands.is_owner()
    async def _set_changelog(self, ctx: commands.Context, changelog: Optional[str]):
        """Get or set current changelog path."""
        if changelog:
            await self.config.changelog_path.set(changelog)
            await ctx.send(f"Changelog path set to '{changelog}'")
        else:
            await ctx.send(
                f"Current changelog path is '{await self.config.changelog_path()}'"
            )

    @github.command(name="set_admin_changelog")
    @commands.is_owner()
    async def _set_admin_changelog(self, ctx: commands.Context, changelog: Optional[str]):
        """Get or set current admin changelog path."""
        if changelog:
            await self.config.admin_changelog_path.set(changelog)
            await ctx.send(f"Admin changelog path set to '{changelog}'")
        else:
            await ctx.send(
                f"Current changelog path is '{await self.config.admin_changelog_path()}'"
            )

    @github.command(name="repo")
    @commands.is_owner()
    async def _repo(self, ctx: commands.Context, repo: Optional[str]):
        """Get or set current repository."""
        if repo:
            await self.config.repo.set(repo)
            await ctx.send(f"Repository set to '{repo}'")
        else:
            await ctx.send(f"Current repository is '{await self.config.repo()}'")

    @property
    async def repo(self):
        return self.gh.get_repo(await self.config.repo())

    @property
    async def branch(self):
        return (await self.repo).get_branch(await self.config.branch())

    def conclusion_emoji(self, conclusion):
        replacements = {
            "action_required": "\N{Three Button Mouse}",
            "cancelled": "\N{No Entry}",
            "failure": "\N{Cross Mark}",
            "neutral": "\N{Neutral Face}",
            "success": "\N{White Heavy Check Mark}",
            "skipped": "\N{Black Right-Pointing Double Triangle}",
            "stale": "\N{Calendar}",
            "timed_out": "\N{Clock Face Four Oclock}",
            None: "\N{Runner}",
        }
        return replacements[conclusion]

    @github.command()
    async def checks(self, ctx: commands.Context, pr: Optional[int]):
        """Shows status of GitHub checks of the default branch or of a PR."""
        commit = None
        mergeable_state = None
        if pr is not None:
            pull_request = (await self.repo).get_pull(pr)
            mergeable_state = pull_request.mergeable_state
            commit = pull_request.head.repo.get_commit(pull_request.head.sha)
        else:
            commit = (await self.branch).commit
        failing_checks = [
            ch
            for ch in commit.get_check_runs()
            if ch.conclusion not in ["success", "skipped"]
        ]
        message = ""
        if not failing_checks:
            message = "All checks succeeding!"
        else:
            message = "\n".join(
                f"{self.conclusion_emoji(ch.conclusion)} **{ch.name}** {ch.conclusion or 'running'}"
                for ch in failing_checks
            )
        if mergeable_state is not None and mergeable_state != "clean":
            message += f"\nMergeable state: {mergeable_state}"
        return await ctx.send(message)

    @github.command()
    async def changelog(self, ctx: commands.Context):
        await self._changelog(ctx, await self.config.changelog_path())

    @github.command()
    async def adminchangelog(self, ctx: commands.Context):
        await self._changelog(ctx, await self.config.admin_changelog_path())

    async def _changelog(self, ctx: commands.Context, path: str):
        """Shows a fancy paginated menu view of the changelog."""
        content = (await self.repo).get_contents(
            path, ref=await self.config.branch()
        )
        content_text = content.decoded_content.decode("utf8")
        content_text = "\n" + content_text.strip()
        lines = content_text.split("\n(")
        embed_colour = await (
            ctx.embed_colour()
            if hasattr(ctx, "embed_colour")
            else self.bot.get_embed_colour(ctx.channel)
        )
        embeds = []
        current_embed = None
        current_entry = None

        def flush_entry():
            nonlocal current_entry
            if current_entry is not None:
                current_embed.add_field(name=current_entry[0], value=current_entry[1])
                current_entry = None

        for line in lines:
            if not line:
                continue
            line_type = line[0]
            line = line[2:]
            if line_type == "t":
                if current_embed:
                    flush_entry()
                    embeds.append(current_embed)
                current_embed = discord.Embed(
                    title=line,
                    color=embed_colour,
                )
            elif line_type == "u":
                flush_entry()
                current_entry = [line, ""]
            elif line_type in ("+", "*"):
                if current_entry[1]:
                    current_entry[1] += "\n"
                if line_type == "+":
                    line = "*" + line + "*"
                current_entry[1] += line
            elif line_type == "e":
                emojis = line
                if "|" in emojis:
                    emojis = emojis.split("|")[0]
                current_entry[0] += " " + emojis
        if current_embed:
            flush_entry()
            embeds.append(current_embed)
        await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    @github.command()
    async def lastcommit(self, ctx: commands.Context, how_far_back: int = 0):
        """Gets the link to the latest commit from the repo or a link to commit some steps back (up to 10)."""
        if how_far_back > 10:
            await ctx.send("Heck no that's too far back, go find that yourself >:(")
            return

        def skip_ignored(commit):
            while "[skip ci]" in commit.commit.message:
                commit = commit.parents[0]
            return commit

        commit = skip_ignored((await self.branch).commit)
        for i in range(how_far_back):
            commit = skip_ignored(commit.parents[0])
        await ctx.send(commit.html_url)

    async def file_url(self, path):
        return f"https://github.com/{await self.config.repo()}/blob/{await self.config.branch()}/{path}"

    @github.command()
    async def file(self, ctx: commands.Context, file: str):
        """Gets a link to files matching the `file` argument. You can also put a line or a line range after a semicolon like `pali.dm:69-420`."""
        async with ctx.typing():
            sha = (await self.branch).commit.sha
            tree = (await self.repo).get_git_tree(sha, recursive=True).tree
            start_line = None
            end_line = None
            if ":" in file:
                file, line = file.split(":")
                if "-" in line:
                    start_line, end_line = line.split("-")
                    start_line = int(start_line)
                    end_line = int(end_line)
                else:
                    start_line = int(line)
            results = []
            for element in tree:
                if (
                    file in element.path.split("/")[-1]
                    or file in element.path
                    and "/" in file
                ):
                    path = element.path
                    name = element.path
                    if start_line:
                        path += f"#L{start_line}"
                        if end_line:
                            path += f"-L{end_line}"
                            name += f" lines {start_line}-{end_line}"
                        else:
                            name += f" line {start_line}"
                    results.append(
                        (
                            name,
                            await self.file_url(path),
                        )
                    )
            embed_colour = await (
                ctx.embed_colour()
                if hasattr(ctx, "embed_colour")
                else self.bot.get_embed_colour(ctx.channel)
            )
            if len(results) > 10:
                results = results[:10] + [("...", "")]
            elif not results:
                results = [("no results found", "")]
            desc = "\n".join(f"[`{name}`]({url})" for name, url in results)
            em = discord.Embed(description=desc, colour=embed_colour)
            await ctx.send(embed=em)

    @github.command(rest_is_raw=True)
    async def randomissue(self, ctx: commands.Context, *, query: str = ""):
        """Picks a random open issue."""
        query = query.strip()
        query += " is:issue is:open repo:" + await self.config.repo()
        async with ctx.typing():
            results = self.gh.search_issues(query, sort="updated", order="desc")
        if not results.totalCount:
            await ctx.send("No issues found.")
            return
        count = min(1000, results.totalCount)
        page_count = math.ceil(count / 30)
        page = results.get_page(random.randint(0, page_count - 1))
        issue = random.choice(page)
        await ctx.send(f"{issue.html_url}\n**#{issue.number}** {issue.title}")

    async def issue_search_menu(
        self, ctx: commands.Context, query, empty_message="No results", title=""
    ):
        embeds = []
        query += " repo:" + await self.config.repo()
        async with ctx.typing():
            results = self.gh.search_issues(query, sort="updated", order="desc")
            embed_colour = await (
                ctx.embed_colour()
                if hasattr(ctx, "embed_colour")
                else self.bot.get_embed_colour(ctx.channel)
            )
            descs = []
            current_desc = ""
            for pull in results:
                line = f"[**#{pull.number}** {pull.title}]({pull.html_url})"
                if len(line) > 4000:
                    line = line[:4000] + "..."
                if len(line) + len(current_desc) > 4000:
                    descs.append(current_desc)
                    current_desc = line
                else:
                    current_desc += "\n" + line
            if current_desc:
                descs.append(current_desc)
            if not descs:
                descs.append(empty_message)
            for i, desc in enumerate(descs):
                embed = discord.Embed(
                    description=desc, colour=embed_colour, title=title
                )
                if len(descs) > 1:
                    embed.set_footer(text=f"page {i+1}/{len(descs)}")
                embeds.append(embed)
        if len(embeds) == 0:
            return
        elif len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    @github.command(rest_is_raw=True)
    async def prs(self, ctx: commands.Context, *, query: str):
        """Searches PRs."""
        query = query.strip()
        await self.issue_search_menu(
            ctx, query + " is:pr", title=f"PRs matching '{query}'"
        )

    @github.command(rest_is_raw=True)
    async def issues(self, ctx: commands.Context, *, query: str):
        """Searches issues."""
        query = query.strip()
        await self.issue_search_menu(
            ctx, query + " is:issue", title=f"Issues matching '{query}'"
        )

    @github.command(aliases=["commit"], rest_is_raw=True)
    async def commits(self, ctx: commands.Context, *, query: str):
        """Searches commits."""
        query = query.strip()
        embeds = []
        MAX_PAGES = 10
        query += " repo:" + await self.config.repo()
        async with ctx.typing():
            results = self.gh.search_commits(query, sort="author-date", order="desc")
            embed_colour = await (
                ctx.embed_colour()
                if hasattr(ctx, "embed_colour")
                else self.bot.get_embed_colour(ctx.channel)
            )
            descs = []
            current_desc = ""
            for commit in results:
                cmsg = commit.commit.message
                cmsg = "\n".join(l.strip() for l in cmsg.split("\n") if l.strip())
                line = f"[**{commit.sha[:7]}**]({commit.html_url}) {cmsg}"
                if len(line) > 4000:
                    line = line[:4000] + "..."
                if len(line) + len(current_desc) > 4000:
                    if current_desc:
                        descs.append(current_desc)
                    if len(descs) >= MAX_PAGES:
                        current_desc = ""
                        break
                    current_desc = line
                else:
                    current_desc += "\n" + line
            if current_desc:
                descs.append(current_desc)
            if not descs:
                descs.append("No results found.")
            for i, desc in enumerate(descs):
                embed = discord.Embed(
                    description=desc, colour=embed_colour, title="Commits"
                )
                if len(descs) > 1:
                    embed.set_footer(text=f"page {i+1}/{len(descs)}")
                embeds.append(embed)
        if len(embeds) == 0:
            return
        elif len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, DEFAULT_CONTROLS, timeout=60.0)

    @github.command()
    async def labelled(self, ctx: commands.Context, label: str):
        """Displays open PRs with a given label."""
        await self.issue_search_menu(
            ctx,
            f'is:pr is:open label:"{label}"',
            title=f"Open PRs with label '{label}'",
        )

    @github.command()
    async def wiki(self, ctx: commands.Context):
        """Displays PRs that have not yet been added to the wiki."""
        await self.issue_search_menu(
            ctx,
            'type:pr is:merged label:"add to wiki"',
            "Nothing to add to the wiki, yay!",
            "PRs that are yet to be added to the wiki",
        )
