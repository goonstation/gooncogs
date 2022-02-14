from redbot.core.bot import Red
from redbot.core.errors import CogLoadError
from .tgs import TGS


async def setup(bot: Red):
    api_tokens = await bot.get_shared_api_tokens("tgs")
    required_keys = {"user", "password", "host"}
    if any(key not in api_tokens for key in required_keys):
        message = (
            "Missing TGS API keys: "
            + ", ".join(required_keys - api_tokens.keys())
            + "\n"
        )
        message += "You need to set RedBot API keys for your TGS instance like this:\n`]set api tgs user,exampleusername password,examplepassword host,https://tgs.example.com`"
        raise CogLoadError(message)
    cog = TGS(bot)
    bot.add_cog(cog)
