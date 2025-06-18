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
ASK_NEW_PLANT_ID, ASK_NEW_PLANT_NAME, ASK_CITY_AND_IO, ASK_GARDEN_SELECTION, ASK_AUTOWATER, ASK_PRESET = range(3,9)
ASK_GARDEN_CONFIRM = 9

async def update_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔒  Authentication check
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    db = current_app.config['DB_SERVICE']

    # 1️⃣  Build the mapping: plant_name (normalised) → plant_id
    plant_dict, pretty_dict= get_user_plants(db, update.effective_user.id)
    context.user_data["plant_dict"] = plant_dict

    #print(pretty_dict)
    # 2️⃣  Build a pretty list of names for the reply
    if not plant_dict:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return ConversationHandler.END

    names = []
    for name in pretty_dict.keys():
        names.append(f"- {name}")

    names_list = "\n".join(names)
    context.user_data["pretty_names"]= names_list
    # 3️⃣  Ask which plant the user wants to update
    await update.message.reply_text(
        f"🪴 Ecco le tue piante registrate:\n{names_list}\n\n"
        "Qual è il *nome* della pianta che vuoi aggiornare?",
        parse_mode="Markdown",
    )

    return ASK_PLANT_NAME


async def update_plant_ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ⌨️ Leggi l'input normalizzato
    plant_name_key = update.message.text.lower().strip()
    
    # 🌱 Recupera il dizionario nome → ID dalle user_data
    plant_dict = context.user_data.get("plant_dict", {})

    # ❌ Se il nome non è tra quelli validi, invia messaggio di errore
    if plant_name_key not in plant_dict:
        plant_names= context.user_data.get("pretty_names")
        await update.message.reply_text(
            f"❌ Nome non valido.\n\nEcco le piante disponibili:\n{plant_names}\n\n"
            "Per favore, inserisci *esattamente* il nome di una delle tue piante.",
            parse_mode="Markdown"
        )
        return ASK_PLANT_NAME  # ← Ripeti la domanda

    # ✅ Se valido, salva il nome e procedi
    context.user_data["plant_name_key"] = plant_name_key

    await update.message.reply_text(
        "📝 Quale campo vuoi aggiornare?\n"
        "- name\n"
        "- description\n"
        "- location (testo descrittivo)\n"
        "- outdoor (sì/no)\n"
        "- auto_watering (sì/no)\n\n"
        "Scrivi il nome del campo. \n"
        "Oppure scrivi /cancel per annullare."
    )
    return ASK_FIELD


async def update_plant_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text.strip().lower()
    valid_fields = ["name", "description", "location", "outdoor", "auto_watering"]

    if field not in valid_fields:
        await update.message.reply_text(
            "❌ Campo non valido. Usa uno tra:\n"
            "- name\n"
            "- description\n"
            "- location\n"
            "- outdoor (sì/no)\n"
            "- auto\\_watering (sì/no)\n\n"
            "Scrivi *esattamente* il nome del campo che vuoi aggiornare.\n"
            "Puoi anche annullare con /cancel.\n",
            parse_mode="Markdown"
        )
        return ASK_FIELD  # 🔁 Resta nello stesso stato

    # ✅ Campo valido → salva e prosegui
    context.user_data["field"] = field

    await update.message.reply_text(
        f"✏️ Inserisci il nuovo valore per *{field}*:\n"
        "Oppure scrivi /cancel per annullare.",
        parse_mode="Markdown"
    )
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

    plant = db.get_dr("plant", plant_id)

     # 🔁 Gestione campo booleano o testuale
    if field in ["auto_watering", "outdoor"]:
        new_value_converted = new_value.lower() in ["sì", "si", "yes", "y", "true", "1"]
        update_dict = {
            "profile": {field: new_value_converted}
        }
        msg_val = "✅ sì" if new_value_converted else "❌ no"
    else:
        update_dict = {
            "profile": {field: new_value}
        }
        msg_val = new_value

    # 🛠️ Aggiorna usando DRFactory
    dr_factory=current_app.config["DR_FACTORY"]
    updated_plant = dr_factory.update_dr(plant, update_dict)
    db.update_dr("plant", plant_id, updated_plant)

    await update.message.reply_text(
        f"✅ Aggiornamento completato: *{field}* → `{msg_val}`",
        parse_mode="Markdown"
    )

    return ConversationHandler.END

async def list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    db = current_app.config['DB_SERVICE']
    _, pretty_dict = get_user_plants(db, telegram_id)  # usa il secondo dizionario, quello con i nomi originali

    if not pretty_dict:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return

    names = []
    for name in pretty_dict.keys():
        names.append(f"- {name}")

    names_list = "\n".join(names)

    await update.message.reply_text(
        f"🪴 Ecco la lista delle tue piante:\n{names_list}",
        parse_mode="Markdown"
    )

async def create_plant2_start(update, context):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    user = get_logged_user(telegram_id)
    gardens = user.get("data", {}).get("owned_gardens", [])
    if not gardens:
        await update.message.reply_text("🌱 Prima di aggiungere una pianta, devi creare almeno un giardino usando /create_garden.")
        return ConversationHandler.END

    context.user_data["user_db"] = user
    context.user_data["gardens"] = gardens

    await update.message.reply_text("🆕 Inserisci l’ID univoco per la pianta:")
    return ASK_NEW_PLANT_ID

# STEP 2
async def create_plant2_ask_name(update, context):
    context.user_data["new_plant_id"] = update.message.text.strip()
    await update.message.reply_text("✏️ Quale nome vuoi dare alla pianta?")
    return ASK_NEW_PLANT_NAME

# STEP 3
async def create_plant2_ask_city_and_io(update, context):
    context.user_data["plant_name"] = update.message.text.strip()
    await update.message.reply_text(
        "📍 Inserisci *città* e se la pianta è *indoor* o *outdoor* (es: `Milano outdoor`)",
        parse_mode="Markdown"
    )
    return ASK_CITY_AND_IO

# STEP 3b
async def parse_city_and_io(update, context):
    text = update.message.text.strip()
    parts = text.split()
    io_token = parts[-1].lower()

    if io_token not in ("indoor", "outdoor"):
        await update.message.reply_text("⚠️ Scrivi la città seguita da 'indoor' o 'outdoor'.")
        return ASK_CITY_AND_IO

    city = " ".join(parts[:-1]).strip()
    if not city:
        await update.message.reply_text("⚠️ Inserisci anche il nome della città.")
        return ASK_CITY_AND_IO

    context.user_data["location"] = city
    context.user_data["outdoor_bool"] = io_token == "outdoor"

    # Se più giardini, chiedi scelta
    gardens = context.user_data.get("gardens", [])
    if len(gardens) > 1:
        db = current_app.config["DB_SERVICE"]
        _, pretty_dict = get_user_gardens(db, update.effective_user.id)
        context.user_data["garden_choices"] = pretty_dict
        garden_list = "\n".join(f"• {name}" for name in pretty_dict.keys())
        await update.message.reply_text(f"🏡 In quale giardino vuoi inserire la pianta?\n{garden_list}\n\nScrivi il nome esatto.")
        return ASK_GARDEN_SELECTION

    # Altrimenti selezione automatica
    dt_id = list(gardens[0].keys())[0]
    context.user_data["target_dt_id"] = dt_id
    await update.message.reply_text("💧 Attivare l’*auto‑watering*? (sì/no)", parse_mode="Markdown")
    return ASK_AUTOWATER

# STEP 4: Garden selection
async def create_plant2_ask_garden(update, context):
    reply = update.message.text.strip()
    choices = context.user_data.get("garden_choices", {})

    for name, dt_id in choices.items():
        if reply.lower() == name.lower():
            context.user_data["target_dt_id"] = dt_id
            await update.message.reply_text("💧 Attivare l’*auto‑watering*? (sì/no)", parse_mode="Markdown")
            return ASK_AUTOWATER

    await update.message.reply_text("⚠️ Giardino non trovato. Riprova.")
    return ASK_GARDEN_SELECTION

# STEP 5: Auto watering
async def ask_preset_handler(update, context):
    response = update.message.text.strip().lower()
    context.user_data["auto_watering"] = response in ("si", "sì", "yes", "y")

    await update.message.reply_text(
                '''🌿 Che tipo di pianta è?
        1. Resilient (poca acqua)
        2. Normal (normale)
        3. Fragile (molta acqua)

        Scrivi 1, 2 o 3.'''
        )
    
    return ASK_PRESET

# STEP 6: Fine
async def create_plant2_finish(update, context):
    preset_map = {
        "1": "resilient",
        "2": "normal",
        "3": "fragile"
    }
    preset_input = update.message.text.strip()
    preset = preset_map.get(preset_input, "normal")

    db = current_app.config['DB_SERVICE']
    dr_factory = current_app.config['DR_FACTORY']
    dt_factory = current_app.config['DT_FACTORY']

    plant_id   = context.user_data["new_plant_id"]
    plant_name = context.user_data["plant_name"]
    location   = context.user_data["location"]
    outdoor    = context.user_data["outdoor_bool"]
    autowater  = context.user_data["auto_watering"]
    dt_id      = context.user_data["target_dt_id"]
    user       = context.user_data["user_db"]

    if db.get_dr("plant", plant_id):
        await update.message.reply_text("⚠️ Esiste già una pianta con questo ID.")
        return ConversationHandler.END

    new_plant = dr_factory.create_dr("plant", {
        "profile": {
            "name": plant_name,
            "owner_id": user["_id"],
            "garden_id": dt_id,
            "description": "",
            "preset": preset,
            "location": location,
            "outdoor": outdoor,
            "auto_watering": autowater
        },
        "metadata": {},
        "data": {}
    })


    new_plant["_id"] = plant_id
    db.save_dr("plant", new_plant)

    user["data"].setdefault("owned_plants", []).append(plant_id)
    db.update_dr("user", user["_id"], user)

    dt_factory.add_digital_replica(dt_id=dt_id, dr_type="plant", dr_id=plant_id)
    config = {"api_key": "05418e63cb684a3a8f2135050250205", "location": location, "preset": preset}
    garden_name = None
    for g in user["data"].get("owned_gardens", []):
        if dt_id in g:
            garden_name = g[dt_id]
            break

    await update.message.reply_text(
        f"✅ Pianta '{plant_name}' creata e inserita nel giardino: <b>{garden_name}</b>.", parse_mode="HTML")
    return ConversationHandler.END




async def cancel_create_plant2(update, context):
    await update.message.reply_text("🚫 Operazione Annullata")
    return ConversationHandler.END




async def universal_fallback(update, context):
    command = update.message.text
    await update.message.reply_text(
        f"⚠️ Il comando `{command}` ha interrotto l'operazione in corso.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END








def get_user_plants(db, telegram_id):

    #Find the user id
    user = get_logged_user(telegram_id)
    if not user:
        return {}                         # user not found → return empty dict

    # Collect all plant IDs owned by this user
    plant_ids = user.get("data", {}).get("owned_plants", [])

    # Fetch all those plant documents from the DB
    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})

    plant_dict = {}
    for plant in plants:
        name = plant["profile"].get("name", "Unnamed Plant").lower().strip()
        plant_dict[name] = plant["_id"]

    pretty_dict = {}
    for plant in plants:
        name = plant["profile"].get("name", "Unnamed Plant")
        pretty_dict[name] = plant["_id"]
    
    return plant_dict, pretty_dict


async def delete_plant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if not context.args:
        await update.message.reply_text("📛 Devi scrivere il nome della pianta da eliminare.\nEsempio: `/delete_plant basilico`", parse_mode="Markdown")
        return

    plant_name_input = " ".join(context.args).lower().strip()

    db = current_app.config['DB_SERVICE']
    dt_factory = current_app.config['DT_FACTORY']
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata tra le tue.")
        return

    # 1️⃣ Rimuovi la DR dal Digital Twin che la contiene
    dt = dt_factory.get_dt_by_plant_id(plant_id)
    dt_id = dt["_id"]
    dt_factory.remove_digital_replica(dt_id=dt_id, dr_id=plant_id)
   

    # 2️⃣ Elimina la DR della pianta
    try:
        db.delete_dr("plant", plant_id)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Errore nella cancellazione della pianta: {str(e)}")
        return

    # 3️⃣ Rimuovi l'ID dalla lista dell'utente
    try:
        user = get_logged_user(telegram_id)
        if user and plant_id in user["data"].get("owned_plants", []):
            user["data"]["owned_plants"].remove(plant_id)
            db.update_dr("user", user["_id"], user)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Pianta cancellata ma errore nella sincronizzazione utente: {str(e)}")
        return

    await update.message.reply_text(f"🗑️ Pianta *{plant_name_input}* eliminata con successo.", parse_mode="Markdown")


# DT Garden Management
def get_user_gardens(db, telegram_id):
    user = get_logged_user(telegram_id)
    if not user:
        return {}, {}

    gardens = user.get("data", {}).get("owned_gardens", [])
    dt_list = db.db["digital_twins"].find({"_id": {"$in": [list(g.keys())[0] for g in gardens]}})

    garden_dict = {}
    pretty_dict = {}

    for dt in dt_list:
        dt_id = dt["_id"]
        name = dt.get("name", "Unnamed Garden")
        garden_dict[name.lower().strip()] = dt_id
        pretty_dict[name] = dt_id

    return garden_dict, pretty_dict

async def create_garden_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_authenticated(user_id):
        await update.message.reply_text("❌ Devi essere autenticato per creare un giardino.")
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Usa il comando così: /create_garden <nome_giardino>")
        return

    garden_name = context.args[0].strip()
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]

    user = get_logged_user(user_id)
    if not user:
        await update.message.reply_text("Errore interno: utente non trovato.")
        return

    # Verifica che non esista già un giardino con questo nome per questo utente
    user_gardens = user["data"].get("owned_gardens", [])
    garden_names = [v for g in user_gardens for v in g.values()]  # estrai solo i nomi
    if garden_name in garden_names:
        await update.message.reply_text(f"⚠️ Hai già un giardino chiamato '{garden_name}'.")
        return

    # Crea il Digital Twin
    dt_id = dt_factory.create_dt(name=garden_name, description=f"Giardino dell'utente {user['_id']}")
    dt_factory.add_service(dt_id, "PlantManagement")
    dt_factory.add_service(dt_id, "GardenHistoryService")
    dt_factory.add_service(dt_id, "GardenStatusService")
    # Aggiungi dizionario {dt_id: garden_name} alla lista
    user["data"].setdefault("owned_gardens", []).append({dt_id: garden_name})
    db.update_dr("user", user["_id"], user)

    await update.message.reply_text(f"🌱 Giardino '{garden_name}' creato con successo!")


async def list_gardens_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = current_app.config["DB_SERVICE"]
    telegram_id = update.effective_user.id
    _, pretty_dict = get_user_gardens(db, telegram_id)

    if not pretty_dict:
        await update.message.reply_text("⚠️ Nessun giardino trovato.")
        return

    text = "<b>🌿 I tuoi giardini:</b>\n" + "\n".join(f"• {name}" for name in pretty_dict.keys())
    await update.message.reply_text(text, parse_mode="HTML")



async def move_plant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    telegram_id = update.effective_user.id

    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("ℹ️ Usa: /moveplant <nome_pianta> <nome_giardino>")
        return

    plant_name = context.args[0].strip().lower()
    garden_name = context.args[1].strip().lower()

    plant_dict, _ = get_user_plants(db, telegram_id)
    garden_dict, _ = get_user_gardens(db, telegram_id)

    if plant_name not in plant_dict:
        await update.message.reply_text("⚠️ Pianta non trovata.")
        return
    if garden_name not in garden_dict:
        await update.message.reply_text("⚠️ Giardino non trovato.")
        return

    plant_id = plant_dict[plant_name]
    garden_id = garden_dict[garden_name]
    new_garden_dt = dt_factory.get_dt(garden_id)

    # 🔁 Rimuovi la DR da tutti gli altri DT
    all_dts = dt_factory.list_dts()
    for dt in all_dts:
        if any(dr["id"] == plant_id and dr["type"] == "plant" for dr in dt["digital_replicas"]):
            db.db["digital_twins"].update_one(
                {"_id": dt["_id"]},
                {"$pull": {"digital_replicas": {"id": plant_id, "type": "plant"}}}
            )

    # ➕ Aggiungi la DR al nuovo DT
    dt_factory.add_digital_replica(new_garden_dt["_id"], "plant", plant_id)

    # 📝 Aggiorna anche il campo garden_id nel profilo della pianta
    plant = db.get_dr("plant", plant_id)
    plant["profile"]["garden_id"] = garden_id
    db.update_dr("plant", plant_id, plant)

    await update.message.reply_text(f"🔁 Pianta spostata nel giardino '{garden_name}'.")


async def garden_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    telegram_id = update.effective_user.id

    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Usa: /gardeninfo <nome_giardino>")
        return

    garden_name = context.args[0].strip().lower()
    garden_dict, _ = get_user_gardens(db, telegram_id)

    if garden_name not in garden_dict:
        await update.message.reply_text("⚠️ Giardino non trovato.")
        return

    dt = dt_factory.get_dt(garden_dict[garden_name])
    plant_ids = [dr["id"] for dr in dt["digital_replicas"] if dr["type"] == "plant"]

    if not plant_ids:
        await update.message.reply_text("🌱 Questo giardino non contiene piante.")
        return

    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})
    names = [p["profile"]["name"] for p in plants]
    text = "<b>🌿 Piante nel giardino:</b>\n" + "\n".join(f"• {n}" for n in names)

    await update.message.reply_text(text, parse_mode="HTML")


async def delete_garden_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return ConversationHandler.END

    if not context.args:
        await update.message.reply_text("ℹ️ Usa: /delete_garden <nome>")
        return ConversationHandler.END

    garden_name = context.args[0].strip().lower()
    db = current_app.config["DB_SERVICE"]
    garden_dict, pretty_dict = get_user_gardens(db, telegram_id)

    if garden_name not in garden_dict:
        await update.message.reply_text("⚠️ Giardino non trovato.")
        return ConversationHandler.END

    dt_id = garden_dict[garden_name]
    context.user_data["target_dt_id"] = dt_id
    context.user_data["target_garden_name"] = [
        k for k, v in pretty_dict.items() if v == dt_id
    ][0]

    await update.message.reply_text(
        f"⚠️ Eliminerai anche tutte le piante contenute nel giardino '{context.user_data['target_garden_name']}'.\n"
        f"Digita <b>SI</b> per confermare.",
        parse_mode="HTML",
    )
    return ASK_GARDEN_CONFIRM


async def delete_garden_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.text.strip().lower()
    if reply != "si":
        await update.message.reply_text("❌ Eliminazione annullata.")
        return ConversationHandler.END

    telegram_id = update.effective_user.id
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]

    dt_id = context.user_data["target_dt_id"]
    garden_name = context.user_data["target_garden_name"]

    # 1. Recupera il DT
    dt = dt_factory.get_dt(dt_id)
    digital_replicas = dt.get("digital_replicas", [])

    # 2. Estrai tutte le plant_id da eliminare
    plant_ids_to_delete = []
    for replica in digital_replicas:
        if replica["type"] == "plant":
            plant_ids_to_delete.append(replica["id"])

    # 3. Elimina le DR di tipo "plant"
    for plant_id in plant_ids_to_delete:
        db.delete_dr("plant", plant_id)

    # 4. Elimina il DT
    db.db["digital_twins"].delete_one({"_id": dt_id})

    # 5. Aggiorna il profilo utente
    user = get_logged_user(telegram_id)

    # Rimuovi il garden dalla lista
    updated_gardens = []
    for entry in user["data"].get("owned_gardens", []):
        if dt_id not in entry:
            updated_gardens.append(entry)
    user["data"]["owned_gardens"] = updated_gardens

    # Rimuovi le piante eliminate dalla lista
    updated_plants = []
    for plant_id in user["data"].get("owned_plants", []):
        if plant_id not in plant_ids_to_delete:
            updated_plants.append(plant_id)
    user["data"]["owned_plants"] = updated_plants

    # Salva utente aggiornato
    db.update_dr("user", user["_id"], user)

    await update.message.reply_text(f"🗑️ Giardino '{garden_name}' e tutte le sue piante sono stati eliminati.")
    return ConversationHandler.END


async def garden_analytics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /garden_analytics <giorni_passati>\nEsempio: /garden_analytics 7")
        return

    try:
        days = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Il numero di giorni deve essere un intero.")
        return

    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    user = get_logged_user(telegram_id)
    gardens = user.get("data", {}).get("owned_gardens", [])

    if not gardens:
        await update.message.reply_text("⚠️ Nessun giardino trovato.")
        return

    if days <= 1:
        range_name = "giorno"
    elif days <= 7:
        range_name = "settimana"
    else:
        range_name = "mese"

    for dt_id, garden_name in gardens.items():
        dt_instance = dt_factory.get_dt_instance(dt_id)
        if not dt_instance:
            continue

        result = dt_instance.execute_service(
            service_name="GardenHistoryService",
            range=range_name
        )

        if not result:
            await update.message.reply_text(f"⚠️ Nessun dato per il giardino '{garden_name}'.")
            continue

        msg = f"📊 Statistiche per il giardino *{garden_name}*:\n\n"
        for plant in result:
            msg += f"🌱 *{plant['plant']}*\n"
            if plant.get("humidity"):
                msg += f"💧 Umidità – min: {plant['humidity']['min']}%, max: {plant['humidity']['max']}%, media: {round(plant['humidity']['mean'], 1)}%\n"
            if plant.get("light"):
                msg += f"💡 Luce – min: {plant['light']['min']}, max: {plant['light']['max']}, media: {round(plant['light']['mean'], 1)}\n"
            msg += "\n"

        await update.message.reply_text(msg, parse_mode="Markdown")


async def garden_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    user = get_logged_user(telegram_id)
    gardens = user.get("data", {}).get("owned_gardens", {})

    if not gardens:
        await update.message.reply_text("⚠️ Nessun giardino trovato.")
        return

    for dt_id, garden_name in gardens.items():
        dt_instance = dt_factory.get_dt_instance(dt_id)
        if not dt_instance:
            continue

        result = dt_instance.execute_service("GardenStatusService")
        if not result:
            await update.message.reply_text(f"⚠️ Nessuna misura disponibile per il giardino '{garden_name}'.")
            continue

        msg = f"📡 Stato attuale del giardino *{garden_name}*:\n\n"
        if "humidity" in result:
            msg += f"💧 Umidità – media: {round(result['humidity']['mean'], 1)}%, sotto soglia: {result['humidity']['below_threshold']} piante\n"
        if "light" in result:
            msg += f"💡 Luce – media: {round(result['light']['mean'], 1)}, sotto soglia: {result['light']['below_threshold']} piante\n"

        await update.message.reply_text(msg, parse_mode="Markdown")