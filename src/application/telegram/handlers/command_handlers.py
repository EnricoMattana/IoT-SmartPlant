
from telegram import Update
from flask import current_app
from telegram.ext import ContextTypes
from datetime import datetime
from src.application.telegram.handlers.login_handlers import is_authenticated
from src.application.telegram.handlers.plant_handlers import get_user_plants
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import InputFile
import statistics
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import asyncio
logger = logging.getLogger(__name__)
OLD_DATA_MIN = 30

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
    payload = "water 10000"

    mqtt_handler.publish(topic, payload)
    await update.message.reply_text(f"💧 Comando `water` inviato a *{plant_name_input}*", parse_mode="Markdown")






async def send_alert_to_user(telegram_id: int, plant_name: str, data, kind: str):
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        if kind=="humidity":
            message = (
                f"⚠️ *Allarme Umidità Bassa!*\n\n"
                f"La tua pianta *{plant_name}* ha raggiunto solo *{data:.1f}%* di umidità.\n"
                f"Controlla se ha bisogno di essere innaffiata 💧"
            )
        elif kind=="light":
            message = (
                f"⚠️ *Allarme Illuminazione Bassa!*\n\n"
                f"La tua pianta *{plant_name}* ha raggiunto solo *{data:.1f}%* di illuminazione.\n"
                f"Controlla se ha bisogno di essere spostata"
            )
        elif kind == "error":
            print(data)
            delta = round(data.get("delta", 0), 1)
            delta=max(0,delta)
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = timestamp.strftime("%H:%M del %d-%m-%Y")
                except Exception:
                    time_str = timestamp
            else:
                time_str = str(timestamp)

            message = (
                f"⚠️ *Possibile anomalia rilevata* sulla pianta *{plant_name}*!\n"
                f"💧 Dopo un'irrigazione, il livello di umidità è aumentato di soli *{delta}%*\n"
                f"🕒 Orario: {time_str}\n"
                f"🔍 Ti consigliamo di controllare che la pompa funzioni correttamente."
            )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")  # ✅ await obbligatorio
        logger.info(f"✅ Notifica Telegram inviata a {telegram_id} per {plant_name}")
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

    plant_name_input = context.args[0].strip()
    try:
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Il numero di giorni deve essere un intero.")
        return

    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    mqtt_handler = current_app.config["MQTT_HANDLER"]

    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input.lower())
    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata.")
        return

    # Controlla freschezza e richiede nuove misure fino a 3 volte
    async def get_last_ts():
        plant_dr = db.get_dr("plant", plant_id)
        meas = plant_dr.get("data", {}).get("measurements", [])
        if not meas:
            return None
        ts = meas[-1].get("timestamp")
        return datetime.fromisoformat(ts) if isinstance(ts, str) else ts

    MAX_TRY = 3
    for i in range(MAX_TRY):
        last_ts = await get_last_ts()
        outdated = not last_ts or (datetime.utcnow() - last_ts > timedelta(minutes=0.5))
        if not outdated:
            break
        await update.message.reply_text(f"⏳ Ultima misura troppo vecchia. Richiesta nuova misura... Tentativo {i+1}")
        mqtt_handler.publish(f"smartplant/{plant_id}/commands", {"command": "send_now"})
        await asyncio.sleep(10)

    # Recupera DT
    dt_data = dt_factory.get_dt_by_plant_id(plant_id)
    dt_instance = dt_factory.get_dt_instance(dt_data["_id"])

    if not dt_instance:
        await update.message.reply_text("⚠️ Digital Twin non disponibile.")
        return

    if days <= 1:
        range_name = "giorno"
    elif days <= 7:
        range_name = "settimana"
    else:
        range_name = "mese"

    result = dt_instance.execute_service(
        service_name="GardenHistoryService",
        range=range_name,
        plant_name=plant_name_input
    )

    if not result or "measurements" not in result:
        await update.message.reply_text("⚠️ Nessun dato utile trovato nel periodo richiesto.")
        return

    def plot_data(data, ylabel, title):
        fig, ax = plt.subplots(figsize=(10, 4))

        if data:
            data.sort(key=lambda x: x["timestamp"])
            times = []
            for m in data:
                ts = m["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                times.append(ts)
            values = [m["value"] for m in data]

            ax.plot(times, values, marker='o', linestyle='-')
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.grid(True)

            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m\n%H:%M'))
            ax.tick_params(axis='x', rotation=45)
            fig.autofmt_xdate()
            fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return buf

    light_data = [m for m in result["measurements"] if m["type"] == "light"]
    humidity_data = [m for m in result["measurements"] if m["type"] == "humidity"]

    def format_stats(label, stats):
        return (f"{label}\n"
                f"📊 Min: {stats['min']:.1f} ({stats['min_time']})\n"
                f"📈 Max: {stats['max']:.1f} ({stats['max_time']})\n"
                f"📉 Media: {stats['mean']:.1f}")

    if light_data:
        buf = plot_data(light_data, "Luce (lux)", f"Luce - {plant_name_input}")
        await update.message.reply_photo(photo=InputFile(buf, filename="light.png"))
        await update.message.reply_text(format_stats("💡 Luce:", result["light"]))

    if humidity_data:
        buf = plot_data(humidity_data, "Umidità (%)", f"Umidità - {plant_name_input}")
        await update.message.reply_photo(photo=InputFile(buf, filename="humidity.png"))
        await update.message.reply_text(format_stats("💧 Umidità:", result["humidity"]))




async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if not is_authenticated(telegram_id):
        await update.message.reply_text("❌ Devi prima fare il login.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /status <nome_pianta>")
        return

    plant_name_input = context.args[0].strip()
    db = current_app.config["DB_SERVICE"]
    dt_factory = current_app.config["DT_FACTORY"]
    mqtt_handler = current_app.config["MQTT_HANDLER"]

    plant_dict, _ = get_user_plants(db, telegram_id)
    plant_id = plant_dict.get(plant_name_input.lower())

    if not plant_id:
        await update.message.reply_text(f"❌ Pianta '{plant_name_input}' non trovata.")
        return

    async def get_last_ts():
        plant_dr = db.get_dr("plant", plant_id)
        meas = plant_dr.get("data", {}).get("measurements", [])
        if not meas:
            return None
        ts = meas[-1].get("timestamp")
        return datetime.fromisoformat(ts) if isinstance(ts, str) else ts

    MAX_TRY=3
    for i in range(0, MAX_TRY):
        last_ts = await get_last_ts()
        outdated = not last_ts or (datetime.utcnow() - last_ts > timedelta(minutes=0.5))
        if outdated:
            await update.message.reply_text(f"⏳ Ultima misura troppo vecchia. Richiesta nuova misura in corso... Tentativo {i+1}")
            mqtt_handler.publish(f"smartplant/{plant_id}/commands", {"command": "send_now"})
            await asyncio.sleep(10)
            last_ts = await get_last_ts()

        # ⚠️ Dopo attesa, controlla se ancora vecchio
        still_old = not last_ts or (datetime.utcnow() - last_ts > timedelta(minutes=0.5))
        if not still_old:
            break

    # ✅ Ora istanzia DT e lancia servizio
    dt_data = dt_factory.get_dt_by_plant_id(plant_id)
    if not dt_data:
        await update.message.reply_text("⚠️ Digital Twin non trovato.")
        return

    dt_instance = dt_factory.get_dt_instance(dt_data["_id"])
    result = dt_instance.execute_service(
        service_name="GardenStatusService",
        plant_name=plant_name_input
    )

    if not result:
        await update.message.reply_text("⚠️ Nessuna misura disponibile.")
        return

    msg = (f"📡 Ultima misura per {plant_name_input}:") + "\n" \
          + f"💧 Umidità: {result['humidity']}%" + "\n" \
          + f"💡 Luce: {result['light']}" + "\n" \
          + f"⏱️ Timestamp: {result['last_updated']}"
    if still_old:
        msg = "⚠️ I dati potrebbero non essere aggiornati!\n\n" + msg

    plant_dr = next(
    (dr for dr in dt_instance.digital_replicas if dr.get("type") == "plant" and dr.get("_id") == plant_id),
    None)

    if plant_dr:
        management_info = plant_dr.get("metadata", {}).get("management_info", {})
        pending = management_info.get("pending_actions", [])

    status_info = []
    auto=plant_dr["profile"].get("auto_watering")
    if "light" in pending:
        status_info.append(
            "🌥️ La luce rilevata è bassa da diverse ore. "
            "Considera di spostare la pianta in una zona più luminosa ☀️"
        )

    if not auto and "humidity" in pending:
        status_info.append(
            "⚠️ L’umidità del terreno è sotto la soglia. "
            "Ti consigliamo di innaffiare la pianta manualmente 💧"
        )

    if auto and management_info.get("disable_aw"):
        status_info.append(
            "🚫 L’auto‑watering è attualmente *sospeso* "
            "perché è prevista pioggia nelle prossime ore ☔️"
        )

    if status_info:
        msg += "\n\n" + "<b>⚠️ Azioni suggerite:</b>\n" + "\n\n".join(status_info)

    await update.message.reply_text(msg, parse_mode="HTML")