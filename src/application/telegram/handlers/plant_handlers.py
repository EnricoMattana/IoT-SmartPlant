from telegram import Update
from flask import current_app
from telegram.ext import ContextTypes, ConversationHandler
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
# Fasi della conversazione per aggiornamento pianta 
ASK_PLANT_NAME, ASK_FIELD, ASK_NEW_VALUE = range(3)
# conversazione /create_plant2
ASK_NEW_PLANT_ID, ASK_NEW_PLANT_NAME, ASK_CITY_AND_IO, ASK_GARDEN_SELECTION, ASK_AUTOWATER, ASK_PRESET = range(3,9)
ASK_GARDEN_CONFIRM = 9

# |------------------------------------------------------------------------------------|
# |----------------------------  UPDATE START -----------------------------------------|
# |------------------------------------------------------------------------------------|

async def update_plant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler per gestire l'update'''
    #  Check dell'autenticazione
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END

    db = current_app.config['DB_SERVICE']

    #  Estraiamo tutte le piante dell'utente in due dizionari
    # - plant_dict ha tutti i nomi normalizzati e in caratteri minuscoli
    # - pretty_dict ha ancora tutti i nomi
    plant_dict, pretty_dict= get_user_plants(db, update.effective_user.id)
    context.user_data["plant_dict"] = plant_dict

    #  Termina la conversazione se l'utente non ha piante
    if not plant_dict:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return ConversationHandler.END
    # Creazione del messaggio
    names = []
    for name in pretty_dict.keys():
        names.append(f"- {name}")
    
    names_list = "\n".join(names)
    context.user_data["pretty_names"]= names_list
    #  
    await update.message.reply_text(
        f"🪴 Ecco le tue piante registrate:\n{names_list}\n\n"
        "Qual è il *nome* della pianta che vuoi aggiornare?",
        parse_mode="Markdown",
    )
    # Return ASK_PLANT_NAME, ovvero passa alla successiva fase della conversazione
    return ASK_PLANT_NAME


async def update_plant_ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Leggi l'input normalizzato
    plant_name_key = update.message.text.lower().strip()
    
    # Recupera il dizionario nome → ID dalle user_data
    plant_dict = context.user_data.get("plant_dict", {})

    # Se il nome non è tra quelli validi, invia messaggio di errore
    if plant_name_key not in plant_dict:
        plant_names= context.user_data.get("pretty_names")
        await update.message.reply_text(
            f"❌ Nome non valido.\n\nEcco le piante disponibili:\n{plant_names}\n\n"
            "Per favore, inserisci *esattamente* il nome di una delle tue piante.",
            parse_mode="Markdown"
        )
        return ASK_PLANT_NAME  # Ripeti la domanda

    # ✅ Se valido, salva il nome e procedi
    context.user_data["plant_name_key"] = plant_name_key

    await update.message.reply_text(
        "📝 Quale campo vuoi aggiornare?\n"
        "- name\n"
        "- description\n"
        "- location (Città)\n"
        "- outdoor (sì/no)\n"
        "- auto_watering (sì/no)\n\n"
        "Scrivi il nome del campo. \n"
        "Oppure scrivi /cancel per annullare."
    )
    return ASK_FIELD


async def update_plant_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text.strip().lower()
    valid_fields = ["name", "description", "location", "outdoor", "auto_watering"]
    # Validazione dell'input
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
        return ASK_FIELD  # Resta nello stesso stato

    # Campo valido -> salva e prosegui
    context.user_data["field"] = field

    await update.message.reply_text(
        f"✏️ Inserisci il nuovo valore per *{field}*:\n"
        "Oppure scrivi /cancel per annullare.",
        parse_mode="Markdown"
    )
    return ASK_NEW_VALUE # Passaggio alla prossima fase


async def update_plant_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Estrazione delle INFO
    new_value = update.message.text.strip()
    field = context.user_data["field"]
    plant_dict = context.user_data["plant_dict"]
    plant_name_key = context.user_data["plant_name_key"]
    plant_id = plant_dict.get(plant_name_key)
    telegram_id = update.effective_user.id
    
    db = current_app.config['DB_SERVICE']
    user = get_logged_user(telegram_id)
    # DEBUG
    if not user:
        await update.message.reply_text("Errore interno: utente non trovato.")
        return ConversationHandler.END

    plant = db.get_dr("plant", plant_id)

    # Gestione campo booleano o testuale
    if field in ["auto_watering", "outdoor"]:
        new_value_converted = new_value.lower() in ["sì", "si", "yes", "y", "true", "1"] # Gestione dei bool
        update_dict = {
            "profile": {field: new_value_converted}
        }
        msg_val = "✅ sì" if new_value_converted else "❌ no"
    else:
        update_dict = {
            "profile": {field: new_value}   # Ovviamente tutti i campi sono in profilo, quindi questa operazione è legittima
        }
        msg_val = new_value

    # Update usando DRFactory
    # Creazione del messaggio
    dr_factory=current_app.config["DR_FACTORY"]
    updated_plant = dr_factory.update_dr(plant, update_dict)
    db.update_dr("plant", plant_id, updated_plant)

    await update.message.reply_text(
        f"✅ Aggiornamento completato: *{field}* → `{msg_val}`",
        parse_mode="Markdown"
    )

    return ConversationHandler.END

# |------------------------------------------------------------------------------------|
# |----------------------------  UPDATE END  ------------------------------------------|
# |------------------------------------------------------------------------------------|


async def list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ''' Handler per ottenere la lista delle piante dell'utente'''
    # Check sull'autenticazione
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return
    db = current_app.config['DB_SERVICE']
    #  Estraiamo tutte le piante dell'utente in due dizionari
    # - plant_dict ha tutti i nomi normalizzati e in caratteri minuscoli
    # - pretty_dict ha ancora tutti i nomi
    _, pretty_dict = get_user_plants(db, telegram_id)  # Usiamo il dizionari pretty

    if not pretty_dict:
        await update.message.reply_text("ℹ️ Non hai ancora registrato nessuna pianta.")
        return

    # Creazione del messaggio
    names = []
    for name in pretty_dict.keys():
        names.append(f"- {name}")

    names_list = "\n".join(names)

    await update.message.reply_text(
        f"🪴 Ecco la lista delle tue piante:\n{names_list}",
        parse_mode="Markdown"
    )

# |------------------------------------------------------------------------------------|
# |--------------------------- START CREAZIONE PIANTA  --------------------------------|
# |------------------------------------------------------------------------------------|
# STEP 1
async def create_plant2_start(update, context):
    # Estrazione del telegram ID
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return ConversationHandler.END
    # Se l'utente non ha ancora un giardino lo deve prima creare
    user = get_logged_user(telegram_id)
    gardens = user.get("data", {}).get("owned_gardens", [])
    if not gardens:
        await update.message.reply_text("🌱 Prima di aggiungere una pianta, devi creare almeno un giardino usando /create_garden.")
        return ConversationHandler.END

    context.user_data["user_db"] = user
    context.user_data["gardens"] = gardens
    # Chiede all'utente di inserire l'ID della pianta, supponendo che venga fornito con il prodotto.
    await update.message.reply_text("🆕 Inserisci l’ID univoco per la pianta:")
    return ASK_NEW_PLANT_ID

# STEP 2
async def create_plant2_ask_name(update, context):
    # Chiediamo il nome della pianta all'utente
    context.user_data["new_plant_id"] = update.message.text.strip()
    await update.message.reply_text("✏️ Quale nome vuoi dare alla pianta?")
    return ASK_NEW_PLANT_NAME

# STEP 3.1
async def create_plant2_ask_city_and_io(update, context):
    # Chiediamo città e se la pianta è da interno o esterno
    context.user_data["plant_name"] = update.message.text.strip()
    await update.message.reply_text(
        "📍 Inserisci *città* e se la pianta è *indoor* o *outdoor* (es: `Cagliari outdoor`)",
        parse_mode="Markdown"
    )
    return ASK_CITY_AND_IO

# STEP 3.2
async def parse_city_and_io(update, context):
    text = update.message.text.strip()
    parts = text.split()
    io_token = parts[-1].lower()
    # Validazione dell'input dell'utente
    if io_token not in ("indoor", "outdoor"):
        await update.message.reply_text("⚠️ Scrivi la città seguita da 'indoor' o 'outdoor'.")
        return ASK_CITY_AND_IO

    city = " ".join(parts[:-1]).strip()
    if not city:
        await update.message.reply_text("⚠️ Inserisci anche il nome della città.")
        return ASK_CITY_AND_IO

    context.user_data["location"] = city
    context.user_data["outdoor_bool"] = io_token == "outdoor"

    # Se più giardini, chiedi in quale giardino inserire la pianta
    gardens = context.user_data.get("gardens")
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

# STEP 4: Selezione del giardino e richiesta di attivazione dell'autowater
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

# STEP 5: Richiesta del preset
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

# STEP 6: Creazione della DR e aggiunta al giardino
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
    garden_name = None
    for g in user["data"].get("owned_gardens", []):
        if dt_id in g:
            garden_name = g[dt_id]
            break

    await update.message.reply_text(
        f"✅ Pianta '{plant_name}' creata e inserita nel giardino: <b>{garden_name}</b>.", parse_mode="HTML") #parsing HTML per sicurezza sui nomi inseriti dall'utente
    return ConversationHandler.END
# |------------------------------------------------------------------------------------|
# |---------------------------   END CREAZIONE PIANTA  --------------------------------|
# |------------------------------------------------------------------------------------|


# Stop della creazione della pianta
async def cancel_create_plant2(update, context):
    await update.message.reply_text("🚫 Operazione Annullata")
    return ConversationHandler.END



# Stop di qualunque operazione
async def universal_fallback(update, context):
    command = update.message.text
    await update.message.reply_text(
        f"⚠️ Il comando `{command}` ha interrotto l'operazione in corso.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END








def get_user_plants(db, telegram_id):
    '''Funzione helper, trova le piante del singolo utente'''

    # Troviamo l'user ID
    user = get_logged_user(telegram_id)

    # Troviamo gli ID di tutte le sue piante
    plant_ids = user.get("data", {}).get("owned_plants", [])

    # Con una query prendiamo le DR associate a tutte le sue piante
    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})
    pretty_dict = {}
    plant_dict = {}
    for plant in plants:
        name = plant["profile"].get("name", "Unnamed Plant").lower().strip()
        plant_dict[name] = plant["_id"]
        name = plant["profile"].get("name", "Unnamed Plant")
        pretty_dict[name] = plant["_id"]
        
    return plant_dict, pretty_dict


async def delete_plant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler per cancellare la DR di una pianta posseduta dall'utente'''
    # Check sull'autenticazione
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return
    # Istruzioni sull'utilizzo
    if not context.args:
        await update.message.reply_text("📛 Devi scrivere il nome della pianta da eliminare.\nEsempio: `/delete_plant basilico`", parse_mode="Markdown")
        return

    plant_name_input = " ".join(context.args).lower().strip()
    # Rimozione della pianta
    db = current_app.config['DB_SERVICE']
    dt_factory = current_app.config['DT_FACTORY']
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata tra le tue.")
        return

    # Rimuoviamo anche la pianta dal Giardino
    dt = dt_factory.get_dt_by_plant_id(plant_id)
    dt_id = dt["_id"]
    dt_factory.remove_digital_replica(dt_id=dt_id, dr_id=plant_id)
   

    # Elimina la DR della pianta
    try:
        db.delete_dr("plant", plant_id)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Errore nella cancellazione della pianta: {str(e)}")
        return

    # Rimuovi la pianta dalla lista delle piante dell'utente
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
    '''Funzione per cercare i giardini dell'utente'''
    user = get_logged_user(telegram_id)

    # Ricerca dei DT posseduti dall'utente
    gardens = user.get("data", {}).get("owned_gardens", [])
    dt_list = db.db["digital_twins"].find({"_id": {"$in": [list(g.keys())[0] for g in gardens]}})

    garden_dict = {}
    pretty_dict = {}
    # Come nel caso della pianta returniamo due dizionari, uno pretty per le stampe e uno per l'elaborazione
    for dt in dt_list:
        dt_id = dt["_id"]
        name = dt.get("name", "Unnamed Garden")
        garden_dict[name.lower().strip()] = dt_id
        pretty_dict[name] = dt_id

    return garden_dict, pretty_dict

async def create_garden_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ''' Hanlder per la creazione del giardino'''
    user_id = update.effective_user.id
    # Check sull'autenticazione
    if not is_authenticated(user_id):
        await update.message.reply_text("❌ Devi essere autenticato per creare un giardino.")
        return

    # Validazione del contenuto del messaggio
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

    # Creazione del Digital Twin
    dt_id = dt_factory.create_dt(name=garden_name, description=f"Giardino dell'utente {user['_id']}")
    # Aggiunta dei servizi
    dt_factory.add_service(dt_id, "PlantManagement")
    dt_factory.add_service(dt_id, "GardenHistoryService")
    dt_factory.add_service(dt_id, "GardenStatusService")
    # Aggiungi dizionario {dt_id: garden_name} alla lista
    user["data"].setdefault("owned_gardens", []).append({dt_id: garden_name})
    db.update_dr("user", user["_id"], user)

    await update.message.reply_text(f"🌱 Giardino '{garden_name}' creato con successo!")


async def list_gardens_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ''' Handler per restituire la lista dei giardini all'utente'''
    db = current_app.config["DB_SERVICE"]
    telegram_id = update.effective_user.id
    _, pretty_dict = get_user_gardens(db, telegram_id)

    if not pretty_dict:
        await update.message.reply_text("⚠️ Nessun giardino trovato.")
        return

    text = "<b>🌿 I tuoi giardini:</b>\n" + "\n".join(f"• {name}" for name in pretty_dict.keys())
    await update.message.reply_text(text, parse_mode="HTML")



async def move_plant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler per spostare una pianta da un giardino all'altro'''
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    telegram_id = update.effective_user.id

    # Check sull'autenticazione
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return
    # Check sul formato del messaggio
    if len(context.args) != 2:
        await update.message.reply_text("ℹ️ Usa: /moveplant <nome_pianta> <nome_giardino>")
        return

    # Check per verificare che l'utente possieda sia la pianta indicata che il giardino   
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

    # Rimuovi la DR dal precedente DT
    dt = dt_factory.get_dt_by_plant_id(plant_id)
    db.db["digital_twins"].update_one(
        {"_id": dt["_id"]},
        {"$pull": {"digital_replicas": {"id": plant_id, "type": "plant"}}}
    )

    # Aggiungi la DR al nuovo DT
    dt_factory.add_digital_replica(new_garden_dt["_id"], "plant", plant_id)

    # Aggiorna anche il campo garden_id nel profilo della pianta
    plant = db.get_dr("plant", plant_id)
    plant["profile"]["garden_id"] = garden_id
    db.update_dr("plant", plant_id, plant)

    await update.message.reply_text(f"🔁 Pianta spostata nel giardino '{garden_name}'.")


async def garden_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    telegram_id = update.effective_user.id

    # Verifica dell'autenticazione
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return
    
    # Check sul formato del messaggio    
    if not context.args:
        await update.message.reply_text("ℹ️ Usa: /gardeninfo <nome_giardino>")
        return

    garden_name = context.args[0].strip().lower()
    garden_dict, _ = get_user_gardens(db, telegram_id)

    if garden_name not in garden_dict:
        await update.message.reply_text("⚠️ Giardino non trovato.")
        return
    # Prendiamo le DR nel giardino e rispondiamo all'utente con la lista delle piante
    dt = dt_factory.get_dt(garden_dict[garden_name])
    plant_ids = [dr["id"] for dr in dt["digital_replicas"] if dr["type"] == "plant"]

    if not plant_ids:
        await update.message.reply_text("🌱 Questo giardino non contiene piante.")
        return

    plants = db.query_drs("plant", {"_id": {"$in": plant_ids}})
    names = [p["profile"]["name"] for p in plants]
    text = "<b>🌿 Piante nel giardino:</b>\n" + "\n".join(f"• {n}" for n in names)

    await update.message.reply_text(text, parse_mode="HTML")

# |------------------------------------------------------------------------------------|
# |-------------------------  START ELIMINAZIONE GIARDINO  ----------------------------|
# |------------------------------------------------------------------------------------|

async def delete_garden_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler per la cancellazione di un giardino'''
    telegram_id = update.effective_user.id
    # Check autenticazione
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi essere autenticato.")
        return ConversationHandler.END
    # Check sul formato del messaggio
    if not context.args:
        await update.message.reply_text("ℹ️ Usa: /delete_garden <nome>")
        return ConversationHandler.END

    garden_name = context.args[0].strip().lower()
    db = current_app.config["DB_SERVICE"]
    garden_dict, _ = get_user_gardens(db, telegram_id)

    if garden_name not in garden_dict:
        await update.message.reply_text("⚠️ Giardino non trovato.")
        return ConversationHandler.END

    dt_id = garden_dict[garden_name]
    context.user_data["target_dt_id"] = dt_id

    context.user_data["target_garden_name"] = context.args[0]
    # Avvisiamo l'utente del fatto che tutte le DR del giardino verranno cancellate
    await update.message.reply_text(
        f"⚠️ Eliminerai anche tutte le piante contenute nel giardino '{context.user_data['target_garden_name']}'.\n"
        f"Digita <b>SI</b> per confermare.",
        parse_mode="HTML",
    )
    return ASK_GARDEN_CONFIRM


async def delete_garden_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.text.strip().lower()
    # Controlliamo la risposta dell'utente
    if reply != "si":
        await update.message.reply_text("❌ Eliminazione annullata.")
        return ConversationHandler.END

    telegram_id = update.effective_user.id
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]

    dt_id = context.user_data["target_dt_id"]
    garden_name = context.user_data["target_garden_name"]

    # Recupera il DT
    dt = dt_factory.get_dt(dt_id)
    digital_replicas = dt.get("digital_replicas", [])

    # Estrai tutte le plant_id da eliminare
    plant_ids_to_delete = []
    for replica in digital_replicas:
        if replica["type"] == "plant":
            plant_ids_to_delete.append(replica["id"])

    # Elimina le DR 
    for plant_id in plant_ids_to_delete:
        db.delete_dr("plant", plant_id)

    # Elimina il DT
    db.db["digital_twins"].delete_one({"_id": dt_id})

    # Aggiorna il profilo utente
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


 