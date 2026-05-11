import os
import re
import sys
import traceback
import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from datetime import time
from zoneinfo import ZoneInfo

# Force les print() à s'afficher immédiatement dans les logs Render
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GUILD_ID = 1486869553081356290
CATEGORIE_VA_ID = 1491532540719140904
PORT = int(os.environ.get("PORT", 8080))

# Heure d'envoi : 19h00 heure française
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
    nom_salon = salon.name.lower()
    pseudo_cible = re.sub(r"^va-", "", nom_salon).strip()

    if not pseudo_cible:
        return None

    for membre in guild.members:
        if membre.bot:
            continue
        if membre.name.lower() == pseudo_cible:
            return membre

    for membre in guild.members:
        if membre.bot:
            continue
        if membre.display_name.lower() == pseudo_cible:
            return membre

    for membre in guild.members:
        if membre.bot:
            continue
        if pseudo_cible in membre.name.lower() or pseudo_cible in membre.display_name.lower():
            return membre

    return None


async def executer_relance():
    print("⏰ === DEBUT RELANCE ===", flush=True)
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            print(f"❌ Serveur introuvable (ID: {GUILD_ID})", flush=True)
            return 0, 0

        print(f"✅ Serveur trouvé : {guild.name}", flush=True)

        try:
            await guild.chunk()
            print(f"📊 Membres chargés : {len(guild.members)}", flush=True)
        except Exception as e:
            print(f"⚠️ Erreur lors du chunk : {e}", flush=True)
            print(f"📊 Membres visibles sans chunk : {len(guild.members)}", flush=True)

        categorie = guild.get_channel(CATEGORIE_VA_ID)
        if categorie is None:
            print(f"❌ Catégorie introuvable (ID: {CATEGORIE_VA_ID})", flush=True)
            return 0, 0
        if not isinstance(categorie, discord.CategoryChannel):
            print(f"❌ {categorie.name} n'est pas une catégorie (type: {type(categorie).__name__})", flush=True)
            return 0, 0

        print(f"✅ Catégorie trouvée : {categorie.name}", flush=True)
        print(f"📂 Salons texte dans la catégorie : {len(categorie.text_channels)}", flush=True)

        envoyes = 0
        erreurs = 0

        for salon in categorie.text_channels:
            try:
                print(f"📨 Traitement de #{salon.name}...", flush=True)
                membre = trouver_membre_du_salon(guild, salon)
                if membre:
                    mention = membre.mention
                    print(f"   ✅ Membre trouvé : {membre.name}", flush=True)
                else:
                    pseudo = re.sub(r"^va-", "", salon.name)
                    mention = f"**{pseudo}**"
                    print(f"   ⚠️ Membre introuvable, fallback : {pseudo}", flush=True)

                message = f"Salut {mention} la forme ?\nComment est-ce que ça avance de ton côté ?"
                await salon.send(message)
                envoyes += 1
                print(f"   ✅ Message envoyé", flush=True)
            except discord.Forbidden:
                erreurs += 1
                print(f"   ❌ Permissions manquantes dans #{salon.name}", flush=True)
            except Exception as e:
                erreurs += 1
                print(f"   ❌ Erreur dans #{salon.name} : {e}", flush=True)
                traceback.print_exc()

        print(f"✅ === FIN RELANCE : {envoyes} envoyés, {erreurs} erreurs ===", flush=True)
        return envoyes, erreurs

    except Exception as e:
        print(f"❌ ERREUR FATALE : {e}", flush=True)
        traceback.print_exc()
        return 0, 0


@tasks.loop(time=HEURE_RELANCE)
async def relance_quotidienne():
    await executer_relance()


@relance_quotidienne.before_loop
async def avant_relance():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    try:
        print(f"✅ Bot connecté : {bot.user}", flush=True)
        print(f"🔍 Recherche du serveur ID {GUILD_ID}...", flush=True)
        
        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            print(f"❌ Serveur {GUILD_ID} INTROUVABLE", flush=True)
            print(f"📋 Serveurs disponibles : {[(g.id, g.name) for g in bot.guilds]}", flush=True)
            return
        
        print(f"✅ Serveur trouvé : {guild.name}", flush=True)
        print(f"🔄 Chargement des membres...", flush=True)
        
        try:
            await guild.chunk()
            print(f"📊 Membres chargés : {len(guild.members)}", flush=True)
        except Exception as e:
            print(f"⚠️ Erreur lors du chunk : {e}", flush=True)
            print(f"📊 Membres visibles sans chunk : {len(guild.members)}", flush=True)

        print(f"⏰ Démarrage de la tâche planifiée...", flush=True)
        if not relance_quotidienne.is_running():
            relance_quotidienne.start()
            print(f"⏰ Tâche planifiée tous les jours à 19h00 (Europe/Paris)", flush=True)
        else:
            print(f"⏰ Tâche déjà en cours", flush=True)
        
        print(f"🎉 === BOT PRÊT ===", flush=True)
        
    except Exception as e:
        print(f"❌ ERREUR FATALE dans on_ready : {e}", flush=True)
        traceback.print_exc()


@bot.command(name="test_relance")
@commands.has_permissions(administrator=True)
async def test_relance(ctx):
    await ctx.send("🧪 Lancement test de la relance...")
    envoyes, erreurs = await executer_relance()
    await ctx.send(f"✅ Test terminé : {envoyes} envoyés, {erreurs} erreurs.")


# ===== LANCEMENT =====
if __name__ == "__main__":
    print("🚀 Démarrage du bot...", flush=True)
    Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
