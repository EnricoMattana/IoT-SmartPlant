from telegram import Update,  KeyboardButton, ReplyKeyboardMarkup
from flask import current_app
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from datetime import datetime

from src.virtualization.digital_replica.dr_factory import DRFactory
import src.application.telegram.handlers.library as lib
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user

# Fasi della conversazione per aggiornamento pianta 
ASK_PLANT_NAME, ASK_FIELD, ASK_NEW_VALUE = range(3)
# conversazione /create_plant2
ASK_NEW_PLANT_ID, ASK_NEW_PLANT_NAME, ASK_NEW_LOCATION, ASK_AUTOWATER = range(3, 7)


async def update_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    db = current_app.config['DB_SERVICE']
    plant_ids, plant_names = get_user_plants(db, update.effective_user.id)  # già lista di nomi
    plant_dict = dict(zip(plant_names, plant_ids))
    context.user_data["plant_dict"] = plant_dict

    if not plant_names:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return ConversationHandler.END

    names_list = "\n".join(f"- {name}" for name in plant_names)

    await update.message.reply_text(
        f"🪴 Ecco le tue piante registrate:\n{names_list}\n\nQual è il *nome* della pianta che vuoi aggiornare?",
        parse_mode="Markdown"
    )

    return ASK_PLANT_NAME


async def update_plant_ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plant_name"] = update.message.text.strip()

    await update.message.reply_text(
        "📝 Quale campo vuoi aggiornare? (name, in/out, description, location)"
    )
    return ASK_FIELD


async def update_plant_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["field"] = update.message.text.strip().lower()

    if context.user_data["field"] not in ["name", "in/out", "description", "location"]:
        await update.message.reply_text("❌ Campo non valido. Usa: name, in/out, description, location")
        return ConversationHandler.END

    await update.message.reply_text(f"✏️ Inserisci il nuovo valore per {context.user_data['field']}:")
    return ASK_NEW_VALUE


async def update_plant_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text.strip()
    field = context.user_data["field"]
    plant_name = context.user_data["plant_name"]
    plant_dict= context.user_data["plant_dict"]
    plant_id = plant_dict.get(plant_name)
    telegram_id = update.effective_user.id

    db = current_app.config['DB_SERVICE']
    user = get_logged_user(telegram_id)

    if not user:
        await update.message.reply_text("Errore interno: utente non trovato.")
        return ConversationHandler.END

    plants = db.query_drs("plant", {"_id": plant_id})

    if not plants:
        await update.message.reply_text("❌ Nessuna pianta trovata con questo ID.")
        return ConversationHandler.END

    plant = plants[0]
    plant["profile"][field] = new_value
    plant["metadata"]["updated_at"] = datetime.utcnow()
    db.update_dr("plant", plant["_id"], plant)

    await update.message.reply_text(f"✅ Aggiornamento completato: {field} -> {new_value}")
    return ConversationHandler.END


async def list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id=update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    db = current_app.config['DB_SERVICE']
    plant_ids, plant_names = get_user_plants(db, telegram_id)  # già lista di nomi
    
    if not plant_names:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return

    names_list = "\n".join(f"- {name}" for name in plant_names)

    await update.message.reply_text(
        f"🪴 Here's the list of your plants!:\n{names_list}\n\nWhich plant do you wish to update?",
        parse_mode="Markdown"
    )



async def create_plant2_start(update, context):
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    await update.message.reply_text("🆕 Inserisci l’ID univoco per la pianta:")
    return ASK_NEW_PLANT_ID


async def create_plant2_ask_name(update, context):
    context.user_data["new_plant_id"] = update.message.text.strip()
    await update.message.reply_text("✏️ Quale nome vuoi dare alla pianta?")
    return ASK_NEW_PLANT_NAME


async def create_plant2_ask_location(update, context):
    context.user_data["plant_name"] = update.message.text.strip()
    await update.message.reply_text("📍 La pianta è *indoor* o *outdoor*?", parse_mode="Markdown")
    return ASK_NEW_LOCATION


async def create_plant2_ask_autowater(update, context):
    location = update.message.text.strip().lower()
    if location not in ("indoor", "outdoor"):
        await update.message.reply_text("⚠️ Scrivi solo *indoor* oppure *outdoor*.")
        return ASK_NEW_LOCATION

    context.user_data["location"] = location
    await update.message.reply_text("💧 Attivare l’*auto-watering*? (sì/no)", parse_mode="Markdown")
    return ASK_AUTOWATER


async def cancel_create_plant2(update, context):
    await update.message.reply_text("🚫 Creazione pianta annullata.")
    return ConversationHandler.END




async def universal_fallback(update, context):
    command = update.message.text
    await update.message.reply_text(
        f"⚠️ Il comando `{command}` ha interrotto l'operazione in corso.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def create_plant2_finish(update, context):
    autowater = update.message.text.strip().lower() in ("si", "sì", "yes", "y")

    plant_id   = context.user_data["new_plant_id"]
    plant_name = context.user_data["plant_name"]
    location   = context.user_data["location"]
    telegram_id = update.effective_user.id

    db = current_app.config['DB_SERVICE']
    if db.get_dr("plant", plant_id):
        await update.message.reply_text("⚠️ Esiste già una pianta con questo ID.")
        return ConversationHandler.END

    user = get_logged_user(telegram_id)
    if not user:
        await update.message.reply_text("Errore interno: utente non trovato.")
        return ConversationHandler.END

    dr_factory = DRFactory("src/virtualization/templates/plant.yaml")
    new_plant = dr_factory.create_dr("plant", {
        "profile": {
            "name": plant_name,
            "owner_id": user["_id"],
            "description": "",
            "species": "unknown",
            "location": location,
            "outdoor": location == "outdoor",
            "auto_watering": autowater          # nuovo campo
        },
        "metadata": {},
        "data": {}
    })
    new_plant["_id"] = plant_id
    db.save_dr("plant", new_plant)

    # collega la pianta all’utente
    user["data"].setdefault("owned_plants", []).append(plant_id)
    db.update_dr("user", user["_id"], user)

    await update.message.reply_text("✅ Pianta creata con successo!")
    return ConversationHandler.END








def get_user_plants(db, telegram_id):
    user=get_logged_user(telegram_id)
    plant_ids = user.get("data", {}).get("owned_plants", [])

    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})
    
    plant_names = [plant["profile"].get("name", "Unnamed Plant") for plant in plants]

    return plant_ids, plant_names






#   /setlocation  -> invia tastiera con bottone "Condividi posizione"
async def setlocation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📍 Invia posizione", request_location=True)]]
    await update.message.reply_text(
        "Condividi la posizione del vaso:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))


async def recv_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    lat, lon = round(loc.latitude, 5), round(loc.longitude, 5)
    await update.message.reply_text(
        f"✅ Posizione salvata: {lat}, {lon}\n"
        "Le prossime previsioni useranno queste coordinate.")
    
