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
    '''Semplice funzione per vedere se l'utente è loggato'''
    return telegram_id in lib.logged_users

def get_logged_user(telegram_id: int):
    ''' Associa L'ID utente del database al telegram ID dell'utente'''
    if telegram_id not in lib.logged_users:
        return None
    user_id = lib.logged_users[telegram_id]
    db = current_app.config['DB_SERVICE']
    return db.get_dr("user", user_id)


async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler di login'''
    try:
        # Estrae il telegram_id dalla conversazione telegram
        telegram_id = update.effective_user.id

        # Check che l'utente non sia già loggato
        if get_logged_user(telegram_id) is not None:
            await update.message.reply_text("Associata al tuo Telegram ID è già presente una sessione aperta!")
            return  
        # Check sulla consistenza del comando
        if len(context.args) != 2:
            await update.message.reply_text("Utilizzo: /login <username> <password>")
            return

        username = context.args[0]
        password = context.args[1]

        # Estrazinoe delle informazioni dell'utente dal database.
        db = current_app.config['DB_SERVICE']
        users = db.query_drs("user", {"profile.username": username})
        if not users:
            await update.message.reply_text("❌ Utente non trovato!")
            return

        # Di default returna una lista
        user = users[0]

        # Si controlla se la password è corretta
        if not check_password_hash(user['profile']['password'], password):
            await update.message.reply_text("❌ Password invalida!")
            return

        # Estrazione dell'ID
        user_id = user['_id']
        
        lib.logged_users[telegram_id] = user_id

        # Aggiornamento info utente
        dr_factory = DRFactory("src/virtualization/templates/user.yaml")
        updated_user = dr_factory.update_dr(user, {
            "profile": {"telegram_id": telegram_id},
            "data": {"last_login": datetime.utcnow()},
            "metadata": {"updated_at": datetime.utcnow()}
        })

        db.update_dr("user", user_id, updated_user)

        await update.message.reply_text(f"✅ Ti sei loggato come {username}\n Attualmente possiedi {len(user['data'].get('owned_plants', []))} piante.")

    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler di logout'''
    telegram_id = update.effective_user.id
    if telegram_id in lib.logged_users:
        del lib.logged_users[telegram_id]
        await update.message.reply_text("🔒 Hai effettuato il logout con successo.")
    else:
        await update.message.reply_text("ℹ️ Non eri loggato.")


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Handler di Registrazione'''
    try:
        # Check sulla consistenza del progetto
        if len(context.args) != 2:
            await update.message.reply_text("Utilizzo: /register <username> <password>")
            return
        
        username = context.args[0]
        password = context.args[1]
        # Verifichiamo che nessun utente abbia già l'username
        db = current_app.config['DB_SERVICE']
        dr_factory_user=current_app.config['DR_FACTORY_USER']
        users = db.query_drs("user", {"profile.username": username})
        if users:
            await update.message.reply_text("❌ Username non disponibile! ")
            return
        # Creiamo il documento utente nel DB
        new_user = dr_factory_user.create_dr("user", {
            "profile": {
                "username": username,
                "password": generate_password_hash(password)
            }
        })
        db.save_dr("user", new_user)
        await update.message.reply_text(f"✅ Registrato con username: {username}. Adesso puoi effettuare il /login")

    except Exception as e:
        await update.message.reply_text(f" Errore: {e}")

