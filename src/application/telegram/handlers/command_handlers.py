
from telegram import Update,  KeyboardButton, ReplyKeyboardMarkup
from flask import current_app
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from datetime import datetime, timedelta
from typing import Callable
from src.virtualization.digital_replica.dr_factory import DRFactory
import src.application.telegram.handlers.library as lib
from src.application.telegram.handlers.login_handlers import is_authenticated, get_logged_user
from src.application.telegram.handlers.plant_handlers import get_user_plants
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import InputFile
import statistics
import matplotlib.dates as mdates


logger = logging.getLogger(__name__)

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







async def analytics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /analytics <nome_pianta> <giorni_passati>\nEsempio: /analytics basilico 7")
        return

    plant_name_input = context.args[0].lower().strip()
    try:
        days = int(context.args[1])
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
    except ValueError:
        await update.message.reply_text("⚠️ Il numero di giorni deve essere un intero.")
        return

    db = current_app.config["DB_SERVICE"]
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)
    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata.")
        return

    plant = db.get_dr("plant", plant_id)
    measurements = plant.get("data", {}).get("measurements", [])

    filtered = []
    for m in measurements:
        try:
            ts = m["timestamp"]
            if start_date <= ts <= end_date:
                filtered.append((ts, m["type"], m["value"]))
        except Exception:
            continue  # Skip malformed timestamps

    if not filtered:
        await update.message.reply_text("ℹ️ Nessuna misura trovata nel periodo indicato.")
        return

    # Ordina le misure per timestamp
    filtered.sort(key=lambda x: x[0])

    light_data = []
    humidity_data = []
    for ts, mtype, val in filtered:
        if mtype == "light":
            light_data.append((ts, val))
        elif mtype == "humidity":
            humidity_data.append((ts, val))

    def compute_stats(data):
        if not data:
            return "Nessun dato."
        values = [v for _, v in data]
        timestamps = [ts for ts, _ in data]
        min_val = min(values)
        max_val = max(values)
        avg_val = round(statistics.mean(values), 1)
        min_time = timestamps[values.index(min_val)].strftime("%d-%m %H:%M")
        max_time = timestamps[values.index(max_val)].strftime("%d-%m %H:%M")
        return f"📊 Min: {min_val} ({min_time})\n📈 Max: {max_val} ({max_time})\n📉 Media: {avg_val}"

    def plot_data(data, ylabel, title):
        fig, ax = plt.subplots(figsize=(10, 4))  # aumenta la larghezza

        if data:
            data.sort(key=lambda x: x[0])
            times, values = zip(*data)

            ax.plot(times, values, marker='o', linestyle='-')
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.grid(True)

            # Formattazione asse X
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m\n%H:%M'))
            ax.tick_params(axis='x', rotation=45)

            # Espansione dei margini automatici
            fig.autofmt_xdate()
            fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return buf

    if light_data:
        buf = plot_data(light_data, "Luce (lux)", f"Luce - {plant_name_input}")
        await update.message.reply_photo(photo=InputFile(buf, filename="light.png"))
        await update.message.reply_text(f"Luce: {compute_stats(light_data)}")

    if humidity_data:
        buf = plot_data(humidity_data, "Umidità (%)", f"Umidità - {plant_name_input}")
        await update.message.reply_photo(photo=InputFile(buf, filename="humidity.png"))
        await update.message.reply_text(f"Umidità: {compute_stats(humidity_data)}")


import asyncio
import json

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /status <nome_pianta>")
        return

    plant_name_input = context.args[0].lower().strip()
    db = current_app.config["DB_SERVICE"]
    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input)

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata.")
        return

    # 1️⃣ Recupera la Digital Replica
    plant = db.get_dr("plant", plant_id)
    measurements = plant.get("data", {}).get("measurements", [])

    last_measurement = max(measurements, key=lambda m: m["timestamp"], default=None)

    # 2️⃣ Controlla timestamp
    too_old = True
    if last_measurement:
        timestamp = last_measurement["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        too_old = datetime.utcnow() - timestamp > timedelta(hours=1)

    if too_old:
        await update.message.reply_text("⌛ Misura vecchia. Invio richiesta alla pianta...")
        # 3️⃣ Invia comando via MQTT
        mqtt_client = current_app.config["MQTT_CLIENT"]
        command_topic = f"smartplant/{plant_id}/commands"
        mqtt_client.publish(command_topic, json.dumps({"command": "send_now"}))

        # 4️⃣ Attendi nuova misura (polling max 10s)
        for _ in range(10):
            await asyncio.sleep(1)
            plant = db.get_dr("plant", plant_id)
            new_measurements = plant.get("data", {}).get("measurements", [])
            newest = max(new_measurements, key=lambda m: m["timestamp"], default=None)
            if newest and newest != last_measurement:
                break
        else:
            await update.message.reply_text("⚠️ Nessuna risposta dalla pianta.")
            return

    # 5️⃣ Mostra stato attuale
    plant = db.get_dr("plant", plant_id)
    measurements = plant.get("data", {}).get("measurements", [])
    latest = max(measurements, key=lambda m: m["timestamp"], default=None)

    if not latest:
        await update.message.reply_text("❌ Nessuna misura trovata.")
        return

    ts = latest["timestamp"]
    if isinstance(ts, datetime):
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts_str = ts

    await update.message.reply_text(
        f"📡 Ultima misura ricevuta:\n"
        f"- Tipo: {latest['type']}\n"
        f"- Valore: {latest['value']}\n"
        f"- Timestamp: {ts_str}"
    )