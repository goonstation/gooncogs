import csv
import os.path
from redbot.core import commands
from redbot.core.bot import Red
from datetime import datetime

class CommandLog(commands.Cog):
    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.log_csv_headers = [
            'time',
            'server_id',
            'server_name',
            'direct',
            'channel_id',
            'channel_name',
            'user_id',
            'user_name',
            'slash_command',
            'command_name',
            'message'
        ]
        self.log_file = 'commands_log.csv'
        if not os.path.isfile(self.log_file):
            with open(self.log_file, 'w') as f:
                writer = csv.DictWriter(f, fieldnames=self.log_csv_headers, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                f.close()

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        server = None
        direct = False
        if ctx.guild:
            server = ctx.guild
        else:
            direct = True
        channel = ctx.channel
        user = ctx.author
        command = ctx.command
        slash_command = False
        message = ''
        if ctx.interaction:
            slash_command = True
            ns = ctx.interaction.namespace
            message = dict(iter(ns))
        else:
            message = ctx.message.clean_content
        
        with open(self.log_file, 'a') as f:
            writer = csv.DictWriter(f, fieldnames=self.log_csv_headers, quoting=csv.QUOTE_ALL)
            writer.writerow({
                'time': datetime.now(),
                'server_id': server.id if server else '',
                'server_name': server.name if server else '',
                'direct': direct,
                'channel_id': channel.id,
                'channel_name': channel.name if hasattr(channel, 'name') else '',
                'user_id': user.id,
                'user_name': user.name,
                'slash_command': slash_command,
                'command_name': command.qualified_name,
                'message': message
            })
            f.close()
        
    # @commands.hybrid_group(name="commandlog")
    # @checks.admin()
    # async def report(self, ctx: commands.Context):
    #     """Show command log history"""
    #     await ctx.defer() if ctx.interaction else await ctx.typing()
    #     with open(self.log_file, 'r') as f:
    #         reader = csv.DictReader(f)
    #         for row in reader:
    #             # do something
