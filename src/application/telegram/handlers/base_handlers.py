from telegram import Update
from telegram.ext import ContextTypes
from src.application.telegram.handlers.login_handlers import is_authenticated

# --- /start command handler ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    await update.message.reply_text(
        "Hello! I am the Smart Plant Bot, peak of electronic engineering evolution <3."
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /help command"""
    user_id = update.effective_user.id

    if is_authenticated(user_id):
        help_text = (
            "<b>🤖 Comandi disponibili (utente autenticato):</b>\n"
            "/start – Avvia il bot\n"
            "/help – Mostra questo messaggio di aiuto\n"
            "/listplants – Elenca le tue piante registrate\n"
            "/create_plant – Crea una nuova pianta\n"
            "/update_plant – Modifica i dati di una pianta\n"
            "/delete_plant – Elimina una pianta\n"
            "/setlocation – Invia la posizione GPS\n"
            "/calibrate_dry – Calibra il sensore a secco\n"
            "/calibrate_wet – Calibra il sensore a bagnato\n"
            "/water – Innaffia una pianta\n"
            "/status – Stato attuale delle tue piante\n"
            "/analytics – Mostra grafici e dati\n"
            "/logout – Esci dal tuo account"
        )
    else:
        help_text = (
            "<b>🔐 Comandi disponibili (non autenticato):</b>\n"
            "/start – Avvia il bot\n"
            "/help – Mostra questo messaggio di aiuto\n"
            "/register – Crea un nuovo account: <code>/register username password</code>\n"
            "/login – Accedi al tuo account: <code>/login username password</code>"
        )

    await update.message.reply_text(help_text, parse_mode="HTML")

# --- Echo handler ---
async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)



