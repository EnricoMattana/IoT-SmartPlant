
from telegram import Update,  KeyboardButton, ReplyKeyboardMarkup
from flask import current_app
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from datetime import datetime
from typing import Callable
from src.virtualization.digital_replica.dr_factory import DRFactory
import src.application.telegram.handlers.library as lib
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
from src.application.telegram.handlers.plant_handlers import get_user_plants
import logging



async def calibrate_dry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if not context.args:
        await update.message.reply_text("📛 Devi scrivere il nome della pianta dopo il comando.\nEsempio: `/calibrate_dry basilico`", parse_mode="Markdown")
        return

    plant_name_input = " ".join(context.args).lower().strip()

    db = current_app.config['DB_SERVICE']
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata tra le tue.")
        return

    mqtt_handler = current_app.config['MQTT_HANDLER']
    topic = f"smartplant/{plant_id}/commands"
    payload = "calDry"

    mqtt_handler.publish(topic, payload)
    await update.message.reply_text(f"✅ Comando `cal_dry` inviato a *{plant_name_input}*", parse_mode="Markdown")



async def calibrate_wet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if not context.args:
        await update.message.reply_text("📛 Devi scrivere il nome della pianta dopo il comando.\nEsempio: `/calibrate_wet basilico`", parse_mode="Markdown")
        return

    plant_name_input = " ".join(context.args).lower().strip()

    db = current_app.config['DB_SERVICE']
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata tra le tue.")
        return

    mqtt_handler = current_app.config['MQTT_HANDLER']
    topic = f"smartplant/{plant_id}/commands"
    payload = "calWet"

    mqtt_handler.publish(topic, payload)
    await update.message.reply_text(f"✅ Comando `cal_wet` inviato a *{plant_name_input}*", parse_mode="Markdown")



async def water_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    # 🔒 Check login
    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    # 📥 Controllo che l'utente abbia inserito il nome
    if not context.args:
        await update.message.reply_text("📛 Devi scrivere il nome della pianta dopo il comando.\nEsempio: `/water basilico`", parse_mode="Markdown")
        return

    plant_name_input = " ".join(context.args).lower().strip()

    # 🔍 Ricava plant_id
    db = current_app.config['DB_SERVICE']
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata tra le tue.")
        return

    # 📤 Pubblica comando MQTT
    mqtt_handler = current_app.config['MQTT_HANDLER']
    topic = f"smartplant/{plant_id}/commands"
    payload = "water"

    mqtt_handler.publish(topic, payload)
    await update.message.reply_text(f"💧 Comando `water` inviato a *{plant_name_input}*", parse_mode="Markdown")




logger = logging.getLogger(__name__)


async def send_humidity_alert_to_user(telegram_id: int, plant_name: str, humidity: float):
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        message = (
            f"⚠️ *Allarme Umidità Bassa!*\n\n"
            f"La tua pianta *{plant_name}* ha raggiunto solo *{humidity:.1f}%* di umidità.\n"
            f"Controlla se ha bisogno di essere innaffiata 💧"
        )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")  # ✅ await obbligatorio
        logger.info(f"✅ Notifica Telegram inviata a {telegram_id} per {plant_name}")
        print("Il telegram ID è", telegram_id)
    except Exception as e:
        logger.error(f"❌ Errore durante invio notifica Telegram: {e}")