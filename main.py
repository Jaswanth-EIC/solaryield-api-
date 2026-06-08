import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from collections import deque
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from twilio.rest import Client
import io
import csv

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Twilio credentials ───────────────────────────────────────────────────────
TWILIO_SID   = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM  = os.environ.get("TWILIO_FROM")
TWILIO_TO    = os.environ.get("TWILIO_TO")

# ─── SMS state ────────────────────────────────────────────────────────────────
# Tracks whether we are currently IN an anomaly state per type.
# SMS fires only on transition: normal→anomaly (onset) and anomaly→normal (recovery)
previous_anomaly_state: dict[str, bool] = {}

# ─── Persistent log ───────────────────────────────────────────────────────────
LOG_BUFFER_SIZE = 8640  # 24 hours at 10s intervals
LOG_FILE        = "solaryield_log.json"
reading_log: deque = deque(maxlen=LOG_BUFFER_SIZE)

def load_log_from_disk():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
                for entry in data[-LOG_BUFFER_SIZE:]:
                    reading_log.append(entry)
            logger.info(f"Loaded {len(reading_log)} readings from disk")
        except Exception as e:
            logger.error(f"Failed to load log: {e}")

def save_log_to_disk():
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(list(reading_log), f)
    except Exception as e:
        logger.error(f"Failed to save log: {e}")

load_log_from_disk()

# ─── SMS helper ───────────────────────────────────────────────────────────────
def send_sms(body: str):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=body, from_=TWILIO_FROM, to=TWILIO_TO)
        logger.info(f"SMS sent: {body[:60]}...")
    except Exception as e:
        logger.error(f"SMS failed: {e}")

def handle_sms(anomaly_type: str, anomaly: bool, temperature: float,
               humidity: float, soil_moisture: float, tilt_angle: int):
    """
    Fire SMS only on state transitions:
    - normal → anomaly: onset message
    - anomaly → normal: recovery message
    No SMS during sustained anomaly (no spam).
    """
    was_anomaly = previous_anomaly_state.get(anomaly_type, False)

    if anomaly and not was_anomaly:
        # Transition: normal → anomaly (ONSET)
        label = anomaly_type.replace("_", " ").title()
        body = (
            f"SolarYield Alert — {label} detected.\n"
            f"Temp: {temperature:.1f}°C, Humidity: {humidity:.1f}%, "
            f"Soil: {soil_moisture:.0f}.\n"
            f"Panel tilted to {tilt_angle}° to protect your crop. "
            f"Will notify you when conditions normalise."
        )
        send_sms(body)
        previous_anomaly_state[anomaly_type] = True

    elif not anomaly and was_anomaly:
        # Transition: anomaly → normal (RECOVERY)
        label = anomaly_type.replace("_", " ").title()
        body = (
            f"SolarYield — {label} resolved.\n"
            f"Temp: {temperature:.1f}°C, Humidity: {humidity:.1f}%, "
            f"Soil: {soil_moisture:.0f}.\n"
            f"Panel returned to baseline position. Crops are stable."
        )
        send_sms(body)
        previous_anomaly_state[anomaly_type] = False

    elif not anomaly and not was_anomaly:
        # Sustained normal — no SMS
        pass

    elif anomaly and was_anomaly:
        # Sustained anomaly — no SMS (no spam)
        pass

# ─── Request schema ───────────────────────────────────────────────────────────
class SensorData(BaseModel):
    temperature:   float
    humidity:      float
    soil_moisture: float
    lux:           float
    voltage:       float
    current:       float
    time_sin:      float
    time_cos:      float

# ─── Growth log ───────────────────────────────────────────────────────────────
GROWTH_FILE = "growth_log.json"
growth_log  = []

def load_growth_log():
    if os.path.exists(GROWTH_FILE):
        try:
            with open(GROWTH_FILE, "r") as f:
                growth_log.extend(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load growth log: {e}")

load_growth_log()

class GrowthEntry(BaseModel):
    condition:  str
    day:        int
    height_cm:  float
    water_ml:   float
    notes:      str = ""

@app.post("/growth")
def log_growth(entry: GrowthEntry):
    sg_time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    record  = {**entry.dict(), "timestamp": sg_time}
    growth_log.append(record)
    try:
        with open(GROWTH_FILE, "w") as f:
            json.dump(growth_log, f)
    except Exception as e:
        logger.error(f"Failed to save growth log: {e}")
    return {"status": "logged", "entry": record}

@app.get("/growth")
def get_growth():
    return {"count": len(growth_log), "entries": growth_log}

# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "SolarYield API running", "log_entries": len(reading_log)}

# ─── Log endpoint ─────────────────────────────────────────────────────────────
@app.get("/log")
def get_log(n: int = 360):
    n = min(n, LOG_BUFFER_SIZE)
    entries = list(reading_log)[-n:]
    return {"count": len(entries), "readings": entries}

# ─── CSV export endpoint ──────────────────────────────────────────────────────
@app.delete("/clear-log")
def clear_log():
    reading_log.clear()
    save_log_to_disk()
    return {"status": "log cleared", "entries_remaining": 0}
@app.get("/export")
def export_csv():
    """Download full log as CSV for daily backup."""
    entries = list(reading_log)
    if not entries:
        return {"error": "No data to export"}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=entries[0].keys())
    writer.writeheader()
    writer.writerows(entries)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=solaryield_log.csv"}
    )

# ─── Predict endpoint ─────────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SensorData):
    tilt         = 5
    anomaly      = False
    anomaly_type = "none"

    logger.info(
        f"Temp: {data.temperature:.1f}C, Hum: {data.humidity:.1f}%, "
        f"Soil: {data.soil_moisture}, Lux: {data.lux:.1f}, "
        f"V: {data.voltage:.2f}, mA: {data.current:.1f}"
    )

    LOW_LIGHT_THRESHOLD = 5000  # update after baseline

    # ── Control policy ────────────────────────────────────────────────────────
    # TODO: Replace with RF model after baseline collection
    if data.temperature > 35:
        tilt         = 25
        anomaly      = True
        anomaly_type = "heat_stress"

    elif data.soil_moisture < 1500:
        tilt         = 25
        anomaly      = True
        anomaly_type = "soil_drought"

    elif data.humidity < 50:
        tilt         = 20
        anomaly      = True
        anomaly_type = "low_humidity"

    elif 0 < data.lux < 3000:
        tilt         = 0
        anomaly      = True
        anomaly_type = "light_deficiency"

    elif data.voltage < 3.0 and data.lux > LOW_LIGHT_THRESHOLD:
        tilt         = 5
        anomaly      = True
        anomaly_type = "voltage_drop"

    elif data.voltage < 3.0 and data.lux <= LOW_LIGHT_THRESHOLD:
        tilt         = 5
        anomaly      = False
        anomaly_type = "irradiance_limited"
        logger.info("Irradiance gate activated")

    # ── SMS — onset and recovery only ────────────────────────────────────────
    handle_sms(anomaly_type, anomaly,
               data.temperature, data.humidity, data.soil_moisture, tilt)

    # ── Log entry ─────────────────────────────────────────────────────────────
    sg_time   = datetime.now(timezone(timedelta(hours=8))).isoformat()
    log_entry = {
        "timestamp":        sg_time,
        "temperature":      data.temperature,
        "humidity":         data.humidity,
        "soil_moisture":    data.soil_moisture,
        "lux":              data.lux,
        "voltage":          data.voltage,
        "current":          data.current,
        "tilt_angle":       tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":     anomaly_type,
        "power_mw":         round(data.voltage * data.current, 2),
    }
    reading_log.append(log_entry)

    if len(reading_log) % 60 == 0:
        save_log_to_disk()

    return {
        "tilt_angle":       tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":     anomaly_type,
        "send_sms":         anomaly,
    }
