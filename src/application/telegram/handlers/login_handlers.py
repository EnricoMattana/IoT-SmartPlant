from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import uuid
from src.virtualization.digital_replica.dr_factory import DRFactory
import src.application.telegram.handlers.library as lib
# Stato utente loggato


def is_authenticated(telegram_id: int):
    return telegram_id in lib.logged_users

def get_logged_user(telegram_id: int):
    if telegram_id not in lib.logged_users:
        return None
    user_id = lib.logged_users[telegram_id]
    db = current_app.config['DB_SERVICE']
    return db.get_dr("user", user_id)


async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        if get_logged_user(telegram_id) is not None:
            await update.message.reply_text("Associated to your telegram ID there's already an open session ")
            return
        
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /login <username> <password>")
            return

        username = context.args[0]
        password = context.args[1]

        db = current_app.config['DB_SERVICE']
        users = db.query_drs("user", {"profile.username": username})
        if not users:
            await update.message.reply_text("❌ User not found")
            return

        user = users[0]
        if not check_password_hash(user['profile']['password'], password):
            await update.message.reply_text("❌ Invalid password")
            return

        user_id = user['_id']
        
        lib.logged_users[telegram_id] = user_id

        dr_factory = DRFactory("src/virtualization/templates/user.yaml")
        updated_user = dr_factory.update_dr(user, {
            "profile": {"telegram_id": telegram_id},
            "data": {"last_login": datetime.utcnow()},
            "metadata": {"updated_at": datetime.utcnow()}
        })

        db.update_dr("user", user_id, updated_user)

        await update.message.reply_text(f"✅ Logged in as {username}\nYou own {len(user['data'].get('owned_plants', []))} plants.")

    except Exception as e:
        await update.message.reply_text(f"Login error: {e}")


async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id in lib.logged_users:
        del lib.logged_users[telegram_id]
        await update.message.reply_text("🔒 You have been logged out.")
    else:
        await update.message.reply_text("ℹ️ You were not logged in.")


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /register <username> <password>")
            return

        username = context.args[0]
        password = context.args[1]

        db = current_app.config['DB_SERVICE']
        users = db.query_drs("user", {"profile.username": username})
        if users:
            await update.message.reply_text("❌ Username already taken")
            return

        user_id = str(uuid.uuid4())
        dr_factory = DRFactory("src/virtualization/templates/user.yaml")
        new_user = dr_factory.create_dr("user", {
            "profile": {
                "username": username,
                "password": generate_password_hash(password)
            },
            "metadata": {
                "status": "active"
            },
            "data": {
                "owned_plants": [],
                "last_login": None
            }
        })

        new_user["_id"] = user_id
        db.save_dr("user", new_user)

        await update.message.reply_text(f"✅ Registered successfully as {username}. Now you can /login")

    except Exception as e:
        await update.message.reply_text(f"Registration error: {e}")


async def create_plant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id

        if not is_authenticated(telegram_id):
            await update.message.reply_text("❌ Devi prima fare il login con /login <username> <password>.")
            return

        if len(context.args) != 3:
            await update.message.reply_text("Usage: /create_plant <plant_id> <plant_name> <indoor|outdoor>")
            return

        plant_id = context.args[0]
        plant_name = context.args[1]
        location_type = context.args[2].strip().lower()

        if location_type not in ["indoor", "outdoor"]:
            await update.message.reply_text("⚠️ The third argument must be either 'indoor' or 'outdoor'.")
            return

        is_outdoor = location_type == "outdoor"

        db = current_app.config['DB_SERVICE']
        dr_factory = DRFactory("src/virtualization/templates/plant.yaml")

        if db.get_dr("plant", plant_id):
            await update.message.reply_text("⚠️ Questa pianta è già registrata.")
            return

        user = get_logged_user(telegram_id)
        if user is None:
            await update.message.reply_text("Errore interno: utente non trovato.")
            return

        new_plant = dr_factory.create_dr("plant", {
            "profile": {
                "name": plant_name,
                "owner_id": lib.logged_users[telegram_id],
                "description": "",
                "species": "unknown",
                "location": location_type,
                "outdoor": is_outdoor
            },
            "metadata": {},
            "data": {}
        })

        new_plant["_id"] = plant_id
        db.save_dr("plant", new_plant)

        user["data"]["owned_plants"].append(plant_id)
        db.update_dr("user", user["_id"], user)

        await update.message.reply_text(
            f"✅ Pianta *{plant_name}* (ID: `{plant_id}`) registrata e collegata al tuo profilo 🌿",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante la creazione della pianta: {str(e)}")

