import platform
from os import environ, listdir, name

import discord
from discord.ext import commands
from dotenv import load_dotenv
from src import logutil

from config import DEBUG, DEV_GUILD

load_dotenv()

TOKEN = environ.get('TOKEN')
APP_ID = environ.get('APP_ID')
environ['TZ'] = 'Europe/Moscow'

logger = logutil.init_logger("bot.py")
logger.debug(
    DEBUG,
)

intents = discord.Intents.default()
intents.members = True

bot = discord.Bot(command_prefix='!', intents=intents, case_insensitive=True, debug_guilds=DEV_GUILD)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(f"Discord.py API version: {discord.__version__}")
    print(f"Python version: {platform.python_version()}")
    print(f"Running on: {platform.system()} {platform.release()} ({name})")
    print("-------------------")


def load_extensions(bot: commands.Bot):
    for filename in listdir("./cogs"):
        try:
            if filename.startswith("_"):
                continue
            if filename.endswith(".py"):
                bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Cog {filename[:-3]} loaded")
            elif "." in filename:
                continue
            else:
                bot.load_extension(f"cogs.{filename}")
        except Exception as e:
            print(f"Extension {filename} not loaded!\nError: {e}")


load_extensions(bot)

bot.run(TOKEN)