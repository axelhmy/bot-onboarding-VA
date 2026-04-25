import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import threading
import asyncio
import os
import re

BOT_TOKEN          = os.environ.get("BOT_TOKEN")
GUILD_ID           = 1486869553081356290
VA_ROLE_ID         = 1488680438938468492
ASSISTANTE_ROLE_ID = 1493625577217720400
MANAGER_VA_ROLE_ID = 1488680497797136384
CEO_ROLE_ID        = 1488680558526468126
CATEGORY_ID        = 1491532540719140904
PORT               = 8080

intents = discord.Intents.default()
intents.members = True
intents.guilds  = True

bot = commands.Bot(command_prefix="!", intents=intents)
app = Flask(__name__)


def extract_fields(data):
    fields = {}
    raw_fields = data.get("data", {}).get("fields", [])

    for field in raw_fields:
        label = field.get("label", "").lower()
        value = field.get("value", "")
        ftype = field.get("type", "")

        # Ignorer les sous-champs checkbox (ceux avec des valeurs booléennes)
        if ftype == "CHECKBOXES" and isinstance(value, bool):
            continue

        # Pour les checkboxes principales, récupérer le texte des options sélectionnées
        if ftype == "CHECKBOXES" and isinstance(value, list):
            options = field.get("options", [])
            selected = [o["text"] for o in options if o["id"] in value]
            value = ", ".join(selected)

        if "discord" in label:
            fields["discord"] = str(value).strip()
        elif "telegram" in label:
            fields["telegram"] = str(value).strip()
        elif "instagram" in label:
            fields["instagram"] = str(value).strip()
        elif "nom" in label or "prénom" in label:
            fields["nom"] = str(value).strip()
        elif "nationalit" in label:
            fields["nationalite"] = str(value).strip()
        elif "modèle" in label or "telephone" in label:
            fields["telephone"] = str(value).strip()
        elif "data" in label or "mobile" in label:
            fields["data_mobile"] = str(value).strip()
        elif "déjà" in label or "travaillé" in label:
            fields["experience"] = str(value).strip()
        elif "heures" in label:
            fields["disponibilite"] = str(value).strip()
        elif "7j" in label:
            fields["semaine"] = str(value).strip()
        elif "niveau" in label:
            fields["niveau"] = str(value).strip()
        elif "payout" in label or "recevoir" in label:
            fields["payout"] = str(value).strip()
        elif "pourquoi" in label or "motivation" in label:
            fields["motivation"] = str(value).strip()
        elif "âge" in label or "age" in label:
            fields["age"] = str(value).strip()

    print(f"Fields extraits: {fields}")
    return fields


def build_embed(fields):
    labels = {
        "telegram": "📱 Telegram",
        "discord": "💬 Discord",
        "instagram": "📸 Instagram",
        "nom": "👤 Nom & Prénom",
        "age": "🎂 Âge",
        "nationalite": "🌍 Nationalité",
        "telephone": "📱 Téléphone",
        "data_mobile": "📶 Data mobile",
        "experience": "💼 Expérience Instagram",
        "disponibilite": "⏰ Disponibilités",
        "semaine": "📅 Disponible 7j/7",
        "niveau": "⭐ Niveau Instagram",
        "payout": "💰 Payout",
        "motivation": "🎯 Motivation",
    }
    embed = discord.Embed(title="📋 Nouvelle candidature VA", color=discord.Color.gold())
    for key, label in labels.items():
        val = fields.get(key, "—") or "—"
        if len(str(val)) > 300:
            val = str(val)[:297] + "..."
        embed.add_field(name=label, value=val, inline=(key != "motivation"))
    embed.set_footer(text="Candidature reçue via Tally.so • OFM Agency")
    return embed


async def process_submission(fields):
    try:
        print("--- DEBUT TRAITEMENT ---")
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print("ERREUR: Serveur introuvable")
            return

        print(f"Serveur: {guild.name}")
        await guild.chunk()
        print(f"Membres: {len(guild.members)}")

        discord_tag = (fields.get("discord") or "").strip().lstrip("@").lower()
        print(f"Recherche: '{discord_tag}'")

        member = None
        for m in guild.members:
            if m.name.lower() == discord_tag or m.display_name.lower() == discord_tag:
                member = m
                print(f"Membre trouve: {m.name}")
                break

        if not member:
            print("Membre non trouve, liste des membres:")
            for m in guild.members:
                print(f"  - name='{m.name}' display='{m.display_name}'")

        # Rôle VA
        if member:
            va_role = guild.get_role(VA_ROLE_ID)
            if va_role:
                await member.add_roles(va_role)
                print("Role VA attribue")

        # Permissions salon
        staff_perm = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
        for role_id in [ASSISTANTE_ROLE_ID, MANAGER_VA_ROLE_ID, CEO_ROLE_ID]:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = staff_perm
        if member:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Nom du salon
        nom = fields.get("nom") or discord_tag or "nouveau-va"
        safe_name = re.sub(r"[^a-z0-9-]", "-", nom.lower().split()[0])
        channel_name = f"va-{safe_name}"

        category = guild.get_channel(CATEGORY_ID)
        print(f"Categorie: {category}")

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )
        print(f"Salon cree: #{channel_name}")

        embed = build_embed(fields)
        mention = member.mention if member else f"**{discord_tag}**"
        msg = f"👋 Bonjour {mention} !\n\nBienvenue dans ton espace privé. Voici ta fiche :\n\u200b"
        if not member:
            msg += f"\n\n⚠️ Pseudo `{discord_tag}` non trouvé sur le serveur."
        await channel.send(msg, embed=embed)

        # DM
        if member:
            try:
                await member.send("✅ **Ta candidature a bien été reçue !**\nUn salon privé vient d'être créé pour toi. Bienvenue dans l'agence 🎉")
            except Exception as e:
                print(f"DM impossible: {e}")

        print("--- FIN OK ---")

    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalide"}), 400
    print("Webhook recu")
    fields = extract_fields(data)
    asyncio.run_coroutine_threadsafe(process_submission(fields), bot.loop)
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "Bot actif", 200


@bot.event
async def on_ready():
    print(f"Bot connecte: {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        await guild.chunk()
        print(f"Serveur: {guild.name} - {len(guild.members)} membres")


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(BOT_TOKEN)
