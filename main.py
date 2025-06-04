from keep_alive import keep_alive
from bot import bot
import os

keep_alive()

token = os.getenv("DISCORD_TOKEN")  # <-- Token aus Railway-Variable
bot.run(token)