from telegram import Update
from telegram.ext import ContextTypes
from src.application.telegram.handlers.login_handlers import is_authenticated

# --- /start command handler ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    message = (
        "🌱 *Ciao! Sono lo Smart Plant Bot!*\n\n"
        "Con me potrai prenderti cura delle tue piante 🌼\n"
        "- Controlla l'umidità\n"
        "- Innaffiale a distanza 💧\n"
        "- Attiva l’irrigazione automatica\n"
        "- Ricevi allarmi in tempo reale\n\n"
        "Premi /help per una panoramica dei comandi disponibili 🛠️"
    )
    await update.message.reply_text(message, parse_mode="Markdown")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /help command"""
    user_id = update.effective_user.id

    if is_authenticated(user_id):
        help_text = (
            "<b>👤 Account & Sessione</b>\n"
            "/logout – Esci dal tuo account\n"

            "<b>🏡 Gestione Giardini</b>\n"
            "/create_garden – Crea un giardino\n"
            "/listgardens – Elenca i tuoi giardini\n"
            "/delete_garden – Elimina un giardino (se vuoto)\n"
            "/gardeninfo – Info piante nel giardino\n\n"



            "<b>🌿 Gestione Piante</b>\n"
            "/listplants – Elenca le tue piante\n"
            "/create_plant – Aggiungi una nuova pianta\n"
            "/update_plant – Modifica info pianta\n"
            "/delete_plant – Elimina una pianta\n"
            "/moveplant – Sposta pianta in altro giardino\n"
            "/calibrate_dry – Calibrazione a secco\n"
            "/calibrate_wet – Calibrazione a bagnato\n"
            "/water – Annaffia una pianta\n\n"

            "<b>📊 Dati e Stato</b>\n"
            "/status – Stato di una pianta\n"
            "/analytics – Statistiche pianta: <code>/analytics nome giorni</code>\n"
        )
    else:
        help_text = (
            "<b>🔐 Comandi disponibili (non autenticato):</b>\n"
            "/start – Avvia il bot\n"
            "/help – Mostra questo messaggio\n"
            "/register – Registrati: <code>/register username password</code>\n"
            "/login – Accedi: <code>/login username password</code>"
        )

    await update.message.reply_text(help_text, parse_mode="HTML")
# --- Echo handler ---
async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)



