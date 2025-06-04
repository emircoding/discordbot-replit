from keep_alive import keep_alive
from bot import bot  # importiere den Bot aus bot.py

keep_alive()  # Starte Webserver für UptimeRobot

bot.run("DEIN_BOT_TOKEN_HIER")  # <-- Ersetze mit deinem Bot-Token