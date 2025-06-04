import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
import sys

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

slots = [f"{(15 + i) % 24:02d}:00 – {(16 + i) % 24:02d}:00" for i in range(11)]
slot_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🔁"]
anmeldungen = {}
slot_user_map = {emoji: [] for emoji in slot_emojis}
teilnahmen = {}
letzte_kanal_ids = {}
letzte_nachricht_ids = {}
gewinner_info = {"name": None, "anzeigen_bis": None}
data_file = "data.json"

def save_data():
    data = {
        "anmeldungen": anmeldungen,
        "slot_user_map": slot_user_map,
        "teilnahmen": teilnahmen,
        "letzte_kanal_ids": letzte_kanal_ids,
        "letzte_nachricht_ids": letzte_nachricht_ids,
        "gewinner_info": gewinner_info,
    }
    with open(data_file, "w") as f:
        json.dump(data, f)

def load_data():
    global anmeldungen, slot_user_map, teilnahmen, letzte_kanal_ids, letzte_nachricht_ids, gewinner_info
    if os.path.isfile(data_file):
        with open(data_file, "r") as f:
            data = json.load(f)
            anmeldungen = data.get("anmeldungen", {})
            slot_user_map = data.get("slot_user_map", {emoji: [] for emoji in slot_emojis})
            teilnahmen = data.get("teilnahmen", {})
            letzte_kanal_ids = data.get("letzte_kanal_ids", {})
            letzte_nachricht_ids = data.get("letzte_nachricht_ids", {})
            gewinner_info = data.get("gewinner_info", {"name": None, "anzeigen_bis": None})

load_data()

def get_datum():
    return datetime.now().strftime("%A, %d. %B %Y")

@bot.event
async def on_ready():
    print(f"{bot.user} ist online!")
    auto_reset.start()
    benachrichtigen.start()

@bot.command()
async def planung(ctx):
    letzte_kanal_ids[ctx.guild.id] = ctx.channel.id
    embed = discord.Embed(title="📦 Schwarzmarkt Planung",
                          description=f"**{get_datum()}**\n\nWähle deine Schicht für heute:",
                          color=0x3498db)
    for emoji, slot in zip(slot_emojis, slots):
        embed.add_field(name=f"{emoji} {slot}", value="—", inline=False)
    msg = await ctx.send(embed=embed)
    for emoji in slot_emojis:
        await msg.add_reaction(emoji)
    letzte_nachricht_ids[ctx.guild.id] = msg.id
    anmeldungen.clear()
    for emoji in slot_user_map:
        slot_user_map[emoji] = []
    save_data()

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.guild_id not in letzte_nachricht_ids or payload.message_id != letzte_nachricht_ids[payload.guild_id]:
        return
    guild = bot.get_guild(payload.guild_id)
    user = guild.get_member(payload.user_id)
    emoji = payload.emoji.name
    channel = bot.get_channel(payload.channel_id)
    heute = datetime.now().strftime("%Y-%m-%d")
    if user and emoji in slot_emojis:
        user_anmeldungen = [info["slot"] for uid, info in anmeldungen.items()
                            if uid == str(user.id) and info["date"] == heute]
        if len(user_anmeldungen) >= 3:
            await channel.send(f"{user.mention}, du hast heute bereits 3 Slots belegt. ❌", delete_after=5)
            return
        if user.display_name not in slot_user_map[emoji]:
            slot_user_map[emoji].append(user.display_name)
            anmeldungen[str(user.id)] = {"slot": emoji, "date": heute}
            teilnahmen[str(user.id)] = teilnahmen.get(str(user.id), 0) + 1
            await aktualisiere_embed(guild.id, channel)
            save_data()

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id not in letzte_nachricht_ids or payload.message_id != letzte_nachricht_ids[payload.guild_id]:
        return
    guild = bot.get_guild(payload.guild_id)
    user = guild.get_member(payload.user_id)
    emoji = payload.emoji.name
    if user and emoji in slot_emojis and user.display_name in slot_user_map[emoji]:
        slot_user_map[emoji].remove(user.display_name)
        anmeldungen.pop(str(user.id), None)
        teilnahmen[str(user.id)] = max(teilnahmen.get(str(user.id), 1) - 1, 0)
        save_data()
        if guild.id in letzte_kanal_ids:
            channel = bot.get_channel(letzte_kanal_ids[guild.id])
            await aktualisiere_embed(guild.id, channel)

async def aktualisiere_embed(guild_id, channel):
    embed = discord.Embed(title="📦 Schwarzmarkt Planung",
                          description=f"**{get_datum()}**\n\nWähle deine Schicht für heute:",
                          color=0x3498db)
    for emoji, slot in zip(slot_emojis, slots):
        users = slot_user_map.get(emoji, [])
        embed.add_field(name=f"{emoji} {slot}", value=", ".join(users) if users else "—", inline=False)
    try:
        message = await channel.fetch_message(letzte_nachricht_ids[guild_id])
        await message.edit(embed=embed)
    except:
        pass

@tasks.loop(minutes=1)
async def auto_reset():
    now = datetime.now()
    if now.hour == 12 and now.minute == 0:
        for guild in bot.guilds:
            if guild.id in letzte_kanal_ids:
                channel = bot.get_channel(letzte_kanal_ids[guild.id])
                if channel:
                    try:
                        if guild.id in letzte_nachricht_ids:
                            try:
                                msg = await channel.fetch_message(letzte_nachricht_ids[guild.id])
                                await msg.delete()
                            except:
                                pass
                        await planung(await bot.get_context(channel.last_message))
                    except:
                        os.execv(sys.executable, ['python'] + sys.argv)

@tasks.loop(minutes=1)
async def benachrichtigen():
    now = datetime.now()
    heute = now.strftime("%Y-%m-%d")
    for i, slot in enumerate(slots):
        slot_start = datetime.combine(now.date(), datetime.strptime(slot.split(" – ")[0], "%H:%M").time())
        if slot_start - timedelta(minutes=5) <= now < slot_start:
            for uid, info in anmeldungen.items():
                if info["slot"] == slot_emojis[i] and info["date"] == heute:
                    for guild in bot.guilds:
                        member = guild.get_member(int(uid))
                        if member and guild.id in letzte_kanal_ids:
                            channel = bot.get_channel(letzte_kanal_ids[guild.id])
                            if channel:
                                await channel.send(f"⏰ {member.mention}, deine Schicht um **{slot}** beginnt in 5 Minuten. Sei bereit!", delete_after=1800)