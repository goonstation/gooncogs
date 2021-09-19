from redbot.core.bot import Red
from redbot.core.errors import CogLoadError
from .tgs import TGS

async def setup(bot: Red):
    api_tokens = await bot.get_shared_api_tokens('test')
    if 'user' not in api_tokens or 'password' not in api_tokens or 'host' not in api_tokens:
        raise CogLoadError( "You need to set RedBot API keys for your TGS instance like this:\n`]set api tgs user,exampleusername password,examplepassword host,https://tgs.example.com`")
    cog = TGS(bot)
    bot.add_cog(cog)

