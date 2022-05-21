import os

import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands

import config
from src import logutil
from src.permissions import Permissions, has_permission

logger = logutil.init_logger(os.path.basename(__file__))


class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    greetings = SlashCommandGroup("greetings", "Various greeting from cogs!")

    international_greetings = greetings.create_subgroup("international", "International greetings")

    @greetings.command()
    async def hello(self, ctx):
        await ctx.respond("Hello, this is a slash subcommand from a cog!")

    @international_greetings.command()
    async def aloha(self, ctx):
        await ctx.respond("Aloha, a Hawaiian greeting")

def setup(bot):
    bot.add_cog(Example(bot))