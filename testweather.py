from datetime import datetime, date
from timezonefinder import TimezoneFinder
import pytz

def convert_local_hour_to_utc_str(time_str: str, lat: float, lon: float) -> str:
    """
    Converte un orario locale tipo "06:12 AM" nella sua ora UTC corrispondente come stringa "HH:MM"
    usando il fuso orario geografico calcolato da latitudine e longitudine.
    """

    # 1. Trova il nome del fuso orario (es. 'Europe/Rome') usando lat/lon
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lon)
    if not timezone_str:
        raise ValueError("Fuso orario non trovato per le coordinate fornite")

    # 2. Parso l’orario ricevuto ("06:12 AM") in oggetto datetime.time
    local_time = datetime.strptime(time_str, "%I:%M %p").time()

    # 3. Combino la data di oggi (UTC) con quell’orario (es. 2025-06-17 + 06:12 AM)
    today = date.today()
    local_dt = datetime.combine(today, local_time)

    # 4. Assegno il fuso orario corretto alla data/ora (timezone-aware datetime)
    tz = pytz.timezone(timezone_str)
    localized_dt = tz.localize(local_dt)

    # 5. Converto il datetime localizzato in UTC
    utc_dt = localized_dt.astimezone(pytz.utc)

    # 6. Estraggo solo l’orario in formato stringa "HH:MM"
    return utc_dt.time()


sunrise_utc = convert_local_hour_to_utc_str("06:12 AM", 45.4642, 9.1900)  # Milano
sunset_utc  = convert_local_hour_to_utc_str("08:45 PM", 45.4642, 9.1900)

print(type(sunrise_utc))
print("Sunrise UTC:", sunrise_utc)  # → "04:12"
print("Sunset UTC:", sunset_utc)    # → "18:45"