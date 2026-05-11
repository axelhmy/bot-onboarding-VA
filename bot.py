import os
import re
import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from datetime import time
from zoneinfo import ZoneInfo

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GUILD_ID = 1486869553081356290
CATEGORIE_VA_ID = 1491532540719140904
PORT = int(os.environ.get("PORT", 8080))

# Heure d'envoi : 19h00 heure française (gère auto été/hiver)
HEURE_RELANCE = time(hour=19, minute=0, tzinfo=ZoneInfo("Europe/Paris"))


# ===== FLASK (keep-alive Render) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot en ligne ✅", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)


# ===== BOT DISCORD =====
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def trouver_membre_du_salon(guild, salon):
    """
    Trouve le VA propriétaire du salon en se basant sur le nom du salon.
    Format attendu : va-{pseudo discord}
    """
    nom_salon = salon.name.lower()
    pseudo_cible = re.sub(r"^va-", "", nom_salon).strip()

    if not pseudo_cible:
        return None

    # 1. Match exact sur le username
    for membre in guild.members:
        if membre.bot:
            continue
        if membre.name.lower() == pseudo_cible:
            return membre

    # 2. Match exact sur le display_name
    for membre in guild.members:
        if membre.bot:
            continue
        if membre.display_name.lower() == pseudo_cible:
            return membre

    # 3. Match partiel en dernier recours
    for membre in guild.members:
        if membre.bot:
            continue
        if pseudo_cible in membre.name.lower() or pseudo_cible in membre.display_name.lower():
            return membre

    return None


@tasks.loop(time=HEURE_RELANCE)
async def relance_quotidienne():
    print("⏰ Déclenchement de la relance quotidienne 19h")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("❌ Serveur introuvable")
        return

    await guild.chunk()

    categorie = guild.get_channel(CATEGORIE_VA_ID)
    if categorie is None or not isinstance(categorie, discord.CategoryChannel):
        print("❌ Catégorie VA introuvable")
        return

    envoyes = 0
    erreurs = 0

    for salon in categorie.text_channels:
        try:
            membre = trouver_membre_du_salon(guild, salon)
            if membre:
                mention = membre.mention
                print(f"✅ Membre trouvé pour #{salon.name} → {membre.name}")
            else:
                pseudo = re.sub(r"^va-", "", salon.name)
                mention = f"**{pseudo}**"
                print(f"⚠️ Membre introuvable pour #{salon.name}, fallback nom brut")

            message = f"Salut {mention} la forme ?\nComment est-ce que ça avance de ton côté ?"
            await salon.send(message)
            envoyes += 1
        except Exception as e:
            erreurs += 1
            print(f"⚠️ Erreur dans #{salon.name} : {e}")

    print(f"✅ Relance terminée : {envoyes} envoyés, {erreurs} erreurs")


@relance_quotidienne.before_loop
async def avant_relance():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        await guild.chunk()
        print(f"📊 Serveur : {guild.name} ({len(guild.members)} membres)")

    if not relance_quotidienne.is_running():
        relance_quotidienne.start()
        print(f"⏰ Tâche planifiée tous les jours à 19h00 (Europe/Paris)")


@bot.command(name="test_relance")
@commands.has_permissions(administrator=True)
async def test_relance(ctx):
    await ctx.send("🧪 Lancement test de la relance...")
    await relance_quotidienne()
    await ctx.send("✅ Test terminé, regarde les logs Render.")


# ===== LANCEMENT =====
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
