import discord
from redbot.core import commands, modlog
from redbot.core.bot import Red


class StopNitroScams(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.sus_messages = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or self.bot.user == message.author:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        valid_user = (
            isinstance(message.author, discord.Member) and not message.author.bot
        )
        if not valid_user:
            return

        if (
            message.guild is None
            or await self.bot.cog_disabled_in_guild(self, message.guild)
            or not hasattr(message.author, "roles")
        ):
            return

        key = message.author.id
        if (
            "http" in message.content.lower()
            and "nitro" in message.content.lower()
            or "everyone" in message.clean_content
        ):
            self.sus_messages[key] = self.sus_messages.get(key, []) + [message]
            msgs = self.sus_messages[key]
            if len(msgs) >= 3:
                if (
                    len(set(msg.content for msg in msgs)) <= len(msgs) - 2
                ):  # at least three are the same
                    for message in msgs:
                        try:
                            await message.delete()
                        except:
                            pass
                    try:
                        await message.author.ban(
                            reason="nitro scam", delete_message_days=0
                        )
                        await message.author.send(
                            f"You have been banned from {message.guild} for Nitro scams, please contact the server administrators once you have improved your account security!"
                        )
                    except:
                        pass
                    case = await modlog.create_case(
                        self.bot,
                        message.guild,
                        message.created_at,
                        action_type="ban",
                        user=message.author,
                        moderator=None,
                        reason=f"Nitro scamming:\n> {message.clean_content}",
                        channel=message.channel,
                    )
                    del self.sus_messages[key]
        else:
            if key in self.sus_messages:
                del self.sus_messages[key]
