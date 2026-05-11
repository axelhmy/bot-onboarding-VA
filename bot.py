import os
import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from datetime import time
from zoneinfo import ZoneInfo

# ===== CONFIG =====
GUILD_ID = 1486869553081356290
CATEGORIE_VA_ID = 1491532540719140904

# Heure d'envoi : 19h00 heure française (Paris gère auto été/hiver)
HEURE_RELANCE = time(hour=19, minute=0, tzinfo=ZoneInfo("Europe/Paris"))

# Message de relance quotidien
MESSAGE_RELANCE = (
    "👋 Salut ! C'est l'heure du point quotidien.\n\n"
    "📊 **Réponds à ces 3 questions :**\n"
    "1️⃣ Qu'est-ce que tu as fait aujourd'hui ?\n"
    "2️⃣ Quels résultats / chiffres ?\n"
    "3️⃣ Un blocage ou une question ?\n\n"
    "À demain 🚀"
)

# ===== FLASK (keep-alive Render) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot en ligne ✅"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ===== BOT DISCORD =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    if not relance_quotidienne.is_running():
        relance_quotidienne.start()
        print(f"⏰ Tâche de relance planifiée tous les jours à {HEURE_RELANCE.strftime('%H:%M')} (Europe/Paris)")

@tasks.loop(time=HEURE_RELANCE)
async def relance_quotidienne():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("❌ Serveur introuvable")
        return

    categorie = guild.get_channel(CATEGORIE_VA_ID)
    if categorie is None or not isinstance(categorie, discord.CategoryChannel):
        print("❌ Catégorie VA introuvable")
        return

    envoyes = 0
    erreurs = 0
    for salon in categorie.text_channels:
        try:
            await salon.send(MESSAGE_RELANCE)
            envoyes += 1
        except Exception as e:
            erreurs += 1
            print(f"⚠️ Erreur dans #{salon.name} : {e}")

    print(f"✅ Relance envoyée : {envoyes} salons OK, {erreurs} erreurs")

@relance_quotidienne.before_loop
async def avant_relance():
    await bot.wait_until_ready()

# Commande de test manuelle (à utiliser pour vérifier sans attendre 19h)
@bot.command(name="test_relance")
@commands.has_permissions(administrator=True)
async def test_relance(ctx):
    await ctx.send("🧪 Lancement test de la relance...")
    await relance_quotidienne()
    await ctx.send("✅ Test terminé, regarde les logs.")

# ===== LANCEMENT =====
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ["BOT_TOKEN"])
