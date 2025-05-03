from telegram import Update,  KeyboardButton, ReplyKeyboardMarkup
from flask import current_app
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from datetime import datetime
from typing import Callable
from src.virtualization.digital_replica.dr_factory import DRFactory
import src.application.telegram.handlers.library as lib
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
# Fasi della conversazione per aggiornamento pianta 
ASK_PLANT_NAME, ASK_FIELD, ASK_NEW_VALUE = range(3)
# conversazione /create_plant2
ASK_NEW_PLANT_ID, ASK_NEW_PLANT_NAME, ASK_CITY_AND_IO, ASK_AUTOWATER = range(3, 7)


async def update_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔒  Authentication check
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    db = current_app.config['DB_SERVICE']

    # 1️⃣  Build the mapping: plant_name (normalised) → plant_id
    plant_dict, pretty_dict= get_user_plants(db, update.effective_user.id)
    context.user_data["plant_dict"] = plant_dict

    print(pretty_dict)
    # 2️⃣  Build a pretty list of names for the reply
    if not plant_dict:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return ConversationHandler.END

    names_list = "\n".join(f"- {name}" for name in pretty_dict.keys())

    # 3️⃣  Ask which plant the user wants to update
    await update.message.reply_text(
        f"🪴 Ecco le tue piante registrate:\n{names_list}\n\n"
        "Qual è il *nome* della pianta che vuoi aggiornare?",
        parse_mode="Markdown",
    )

    return ASK_PLANT_NAME


async def update_plant_ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # normalise the user input exactly like in the dict
    plant_name_key = update.message.text.lower().strip()
    context.user_data["plant_name_key"] = plant_name_key

    await update.message.reply_text(
        "📝 Quale campo vuoi aggiornare?\n"
        "- name\n"
        "- description\n"
        "- location (testo descrittivo)\n"
        "- outdoor (sì/no)\n"
        "- auto_watering (sì/no)\n\n"
        "Scrivi il nome del campo:"
    )
    return ASK_FIELD


async def update_plant_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text.strip().lower()
    context.user_data["field"] = field

    valid_fields = ["name", "description", "location", "outdoor", "auto_watering"]
    if field not in valid_fields:
        await update.message.reply_text("❌ Campo non valido. Usa uno tra: name, description, location, outdoor, auto_watering")
        return ConversationHandler.END

    await update.message.reply_text(f"✏️ Inserisci il nuovo valore per *{field}*:", parse_mode="Markdown")
    return ASK_NEW_VALUE


async def update_plant_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text.strip()
    field = context.user_data["field"]
    plant_dict = context.user_data["plant_dict"]
    plant_name_key = context.user_data["plant_name_key"]
    plant_id = plant_dict.get(plant_name_key)
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

    # 🔁 Gestione dei campi booleani
    if field in ["auto_watering", "outdoor"]:
        new_bool = new_value.lower() in ["sì", "si", "yes", "y", "true", "1"]
        plant["profile"][field] = new_bool
        msg_val = "✅ sì" if new_bool else "❌ no"

    else:
        # name, description, location
        plant["profile"][field] = new_value
        msg_val = new_value

    plant["metadata"]["updated_at"] = datetime.utcnow()
    db.update_dr("plant", plant["_id"], plant)

    await update.message.reply_text(f"✅ Aggiornamento completato: *{field}* → `{msg_val}`", parse_mode="Markdown")
    await sync_dt_with_plant_update(
        plant=plant,
        plant_id=plant_id,
        send_msg=update.message.reply_text
    )

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



# ──────────────────────────────────────────────────────────────
# STEP 1  ▸  ask for a unique plant‑ID  (unchanged)
# ──────────────────────────────────────────────────────────────
async def create_plant2_start(update, context):
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    await update.message.reply_text("🆕 Inserisci l’ID univoco per la pianta:")
    return ASK_NEW_PLANT_ID


# ──────────────────────────────────────────────────────────────
# STEP 2  ▸  ask for the plant name  (unchanged)
# ──────────────────────────────────────────────────────────────
async def create_plant2_ask_name(update, context):
    context.user_data["new_plant_id"] = update.message.text.strip()
    await update.message.reply_text("✏️ Quale nome vuoi dare alla pianta?")
    return ASK_NEW_PLANT_NAME


# ──────────────────────────────────────────────────────────────
# STEP 3  ▸  ask for BOTH city and indoor/outdoor  (new logic)
# ──────────────────────────────────────────────────────────────
async def create_plant2_ask_city_and_io(update, context):
    """
    Expect a single line like:
        'Milan outdoor'
        'Cagliari indoor'
    Parse it into:
        location = 'Milan'          # city / free text
        outdoor  = True / False     # bool
    """
    context.user_data["plant_name"] = update.message.text.strip()

    await update.message.reply_text(
        "📍 Inserisci *città* e se la pianta è *indoor* o *outdoor*.\n"
        "Esempi:\n"
        "`Milan outdoor`\n"
        "`Cagliari indoor`",
        parse_mode="Markdown",
    )
    return ASK_CITY_AND_IO


# ──────────────────────────────────────────────────────────────
# STEP 3b ▸  validate & store city + io
# ──────────────────────────────────────────────────────────────
async def parse_city_and_io(update, context):
    """
    Split the message; last token must be 'indoor' or 'outdoor'.
    Everything before it is considered the city / location string.
    """
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("⚠️ Il testo non può essere vuoto.")
        return ASK_CITY_AND_IO

    # Separate by whitespace – city might contain spaces (‘San Benedetto del Tronto outdoor’)
    parts = text.split()
    io_token = parts[-1].lower()

    if io_token not in ("indoor", "outdoor"):
        await update.message.reply_text(
            "⚠️ Specifica *indoor* o *outdoor* alla fine.\nEsempio: `Milan outdoor`",
            parse_mode="Markdown"
        )
        return ASK_CITY_AND_IO

    city = " ".join(parts[:-1]).strip()
    if not city:
        await update.message.reply_text("⚠️ Inserisci anche il nome della città.")
        return ASK_CITY_AND_IO

    # Save both pieces in user_data for the final step
    context.user_data["location"] = city                 # ex. 'Milan'
    context.user_data["outdoor_bool"] = io_token == "outdoor"

    # Move on to the auto‑watering question
    await update.message.reply_text("💧 Attivare l’*auto‑watering*? (sì/no)", parse_mode="Markdown")
    return ASK_AUTOWATER


# ──────────────────────────────────────────────────────────────
# STEP 4 ▸  finish creation  (minor edits only)
# ──────────────────────────────────────────────────────────────
async def create_plant2_finish(update, context):
    autowater = update.message.text.strip().lower() in ("si", "sì", "yes", "y")

    plant_id   = context.user_data["new_plant_id"]
    plant_name = context.user_data["plant_name"]
    location   = context.user_data["location"]          # city string
    outdoor    = context.user_data["outdoor_bool"]      # bool
    telegram_id = update.effective_user.id

    db = current_app.config['DB_SERVICE']

    # --- (same validation & DR creation as before) -------------------------
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
            "name":          plant_name,
            "owner_id":      user["_id"],
            "description":   "",
            "species":       "unknown",
            "location":      location,      # city
            "outdoor":       outdoor,       # bool
            "auto_watering": autowater
        },
        "metadata": {},
        "data": {}
    })
    new_plant["_id"] = plant_id
    db.save_dr("plant", new_plant)

    # attach plant to user
    user["data"].setdefault("owned_plants", []).append(plant_id)
    db.update_dr("user", user["_id"], user)

    # --- DIGITAL TWIN & SERVICES ------------------------------------------
    dt_factory = current_app.config['DT_FACTORY']
    dt_name = f"DT_plant_{plant_id}"
    dt_id = dt_factory.create_dt(name=dt_name)

    dt_factory.add_digital_replica(dt_id=dt_id, dr_type="plant", dr_id=plant_id)

    # add services according to profile
    if outdoor:
        dt_factory.add_service(dt_id, "WeatherForecastService",
                               {"location": location})   # pass city
    if autowater:
        dt_factory.add_service(dt_id, "AutoWateringService")

    await update.message.reply_text("✅ Pianta creata con successo!")
    return ConversationHandler.END



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









def get_user_plants(db, telegram_id):

    """
    Return a dict that maps each plant *name* (lower‑cased, stripped)
    to its unique plant *ID* for the given Telegram user.
    """

    #Find the user id
    user = get_logged_user(telegram_id)
    if not user:
        return {}                         # user not found → return empty dict

    # Collect all plant IDs owned by this user
    plant_ids = user.get("data", {}).get("owned_plants", [])

    # Fetch all those plant documents from the DB
    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})

    # Build and return a safe mapping name → id
    # The name is taken from the plant profile, and the mapping
    # is case‑insensitive and ignores leading/trailing spaces
    plant_dict = {}
    for plant in plants:
        name = plant["profile"].get("name", "Unnamed Plant").lower().strip()
        plant_dict[name] = plant["_id"]

    pretty_dict = {}
    for plant in plants:
        name = plant["profile"].get("name", "Unnamed Plant")
        pretty_dict[name] = plant["_id"]
    
    return plant_dict, pretty_dict






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
    


async def sync_dt_with_plant_update(plant: dict, plant_id: str, send_msg: Callable):
    """
    Sincronizza i servizi del DT associato a una pianta, in base a:
    - outdoor: aggiunge/rimuove WeatherForecastService
    - location: aggiorna il servizio se outdoor resta True ma cambia
    - auto_watering: aggiunge/rimuove AutoWateringService

    Args:
        plant: dict aggiornato della pianta (DR)
        plant_id: ID della pianta
        send_msg: funzione async per inviare messaggi Telegram all’utente
    """
    from flask import current_app
    dt_factory = current_app.config['DT_FACTORY']
    dts = dt_factory.list_dts()

    for dt_data in dts:
        for dr_ref in dt_data.get("digital_replicas", []):
            if dr_ref["id"] == plant_id and dr_ref["type"] == "plant":
                dt_id = dt_data["_id"]
                try:
                    dt_instance = dt_factory.get_dt_instance(dt_id)
                    services = dt_instance.list_services()

                    outdoor = plant["profile"].get("outdoor", False)
                    auto_watering = plant["profile"].get("auto_watering", False)
                    new_location = plant["profile"].get("location", "Milan")

                    added, removed, updated = [], [], []

                    # === WEATHER FORECAST SERVICE ===
                    if outdoor:
                        if "WeatherForecastService" not in services:
                            dt_factory.add_service(dt_id, "WeatherForecastService", {
                                "api_key": "05418e63cb684a3a8f2135050250205",
                                "location": new_location,
                                "rain_threshold": 50
                            })
                            added.append("WeatherForecastService")
                        else:
                            # Se esiste, controlla se la location è cambiata → rimuovi e ricrea
                            dt = dt_factory.get_dt(dt_id)
                            for s in dt.get("services", []):
                                if s["name"] == "WeatherForecastService":
                                    old_loc = s.get("config", {}).get("location", "")
                                    if old_loc != new_location:
                                        dt_factory.remove_service(dt_id, "WeatherForecastService")
                                        removed.append("WeatherForecastService")

                                        dt_factory.add_service(dt_id, "WeatherForecastService", {
                                            "api_key": "05418e63cb684a3a8f2135050250205",
                                            "location": new_location,
                                            "rain_threshold": 50
                                        })
                                        added.append("WeatherForecastService (location aggiornata)")
                    else:
                        if "WeatherForecastService" in services:
                            dt_factory.remove_service(dt_id, "WeatherForecastService")
                            removed.append("WeatherForecastService")
                    # === AUTO WATERING SERVICE ===
                    if auto_watering:
                        if "AutoWateringService" not in services:
                            dt_factory.add_service(dt_id, "AutoWateringService")
                            added.append("AutoWateringService")
                    else:
                        if "AutoWateringService" in services:
                            dt_factory.remove_service(dt_id, "AutoWateringService")
                            removed.append("AutoWateringService")

                    # === MESSAGGIO ALL’UTENTE ===
                    msg_lines = []
                    if added:
                        msg_lines.append(f"✅ Servizi aggiunti: {', '.join(added)}")
                    if updated:
                        msg_lines.append(f"🔄 Servizi aggiornati: {', '.join(updated)}")
                    if removed:
                        msg_lines.append(f"🗑️ Servizi rimossi: {', '.join(removed)}")
                    if not msg_lines:
                        msg_lines.append("ℹ️ Il Digital Twin è già allineato.")

                    await send_msg("\n".join(msg_lines))

                except Exception as e:
                    await send_msg(f"⚠️ Errore durante la sincronizzazione DT: {str(e)}")

                return  # trovato e gestito il DT
