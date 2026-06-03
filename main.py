import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from collections import deque
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.rest import Client

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ─── CORS — allow Streamlit to poll this API ──────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Twilio credentials from environment variables ────────────────────────────
TWILIO_SID   = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM  = os.environ.get("TWILIO_FROM")
TWILIO_TO    = os.environ.get("TWILIO_TO")

# ─── SMS throttle state ───────────────────────────────────────────────────────
last_sms_time: dict[str, float] = {}
SMS_COOLDOWN_SECONDS = 3600  # 1 hour per anomaly type

# ─── Persistent log — in-memory ring buffer + JSON file on disk ───────────────
# Ring buffer: last 8640 readings = 24 hours at 10s intervals
LOG_BUFFER_SIZE = 8640
LOG_FILE        = "solaryield_log.json"
reading_log: deque = deque(maxlen=LOG_BUFFER_SIZE)

# Load existing log from disk on startup (survives Render restarts)
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
def send_sms(anomaly_type: str, temperature: float, humidity: float,
             soil_moisture: float, tilt_angle: int):
    current_time = time.time()
    last_sent    = last_sms_time.get(anomaly_type, 0)

    if current_time - last_sent < SMS_COOLDOWN_SECONDS:
        seconds_remaining = int(SMS_COOLDOWN_SECONDS - (current_time - last_sent))
        logger.info(f"SMS throttled for '{anomaly_type}' — {seconds_remaining}s remaining")
        return

    try:
        client  = Client(TWILIO_SID, TWILIO_TOKEN)
        message = (
            f"SolarYield Alert: {anomaly_type}. "
            f"Temp: {temperature:.1f}C, "
            f"Humidity: {humidity:.1f}%, "
            f"Soil: {soil_moisture}. "
            f"Panel tilted to {tilt_angle} degrees."
        )
        client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)
        last_sms_time[anomaly_type] = current_time
        logger.info(f"SMS sent: {anomaly_type}")
    except Exception as e:
        logger.error(f"SMS failed: {e}")

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

# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "SolarYield API running", "log_entries": len(reading_log)}

# ─── Log endpoint — Streamlit polls this ──────────────────────────────────────
@app.get("/log")
def get_log(n: int = 360):
    """Return last n readings (default 360 = 1 hour). Max 8640 = 24 hours."""
    n = min(n, LOG_BUFFER_SIZE)
    entries = list(reading_log)[-n:]
    return {"count": len(entries), "readings": entries}

# ─── Growth log — manual plant measurements ───────────────────────────────────
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
    condition:    str   # "A", "B", or "C"
    day:          int
    height_cm:    float
    water_ml:     float
    notes:        str = ""

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

# ─── Predict endpoint ─────────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SensorData):
    tilt         = 5
    anomaly      = False
    anomaly_type = "none"

    logger.info(
        f"Received — Temp: {data.temperature:.1f}C, Hum: {data.humidity:.1f}%, "
        f"Soil: {data.soil_moisture}, Lux: {data.lux:.1f}, "
        f"V: {data.voltage:.2f}, mA: {data.current:.1f}"
    )

    # ── Irradiance gate threshold ──────────────────────────────────────────────
    # NOTE: Update after 5-day baseline collection
    LOW_LIGHT_THRESHOLD = 5000  # lux placeholder

    # ── Control policy — placeholder threshold logic ───────────────────────────
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
        logger.info("Irradiance gate activated — suppressing voltage tilt")

    # ── Append to log ─────────────────────────────────────────────────────────
    sg_time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    log_entry = {
        "timestamp":       sg_time,
        "temperature":     data.temperature,
        "humidity":        data.humidity,
        "soil_moisture":   data.soil_moisture,
        "lux":             data.lux,
        "voltage":         data.voltage,
        "current":         data.current,
        "tilt_angle":      tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":    anomaly_type,
        "power_mw":        round(data.voltage * data.current, 2),
    }
    reading_log.append(log_entry)

    # Save to disk every 60 readings (~10 minutes)
    if len(reading_log) % 60 == 0:
        save_log_to_disk()

    # ── SMS alert ─────────────────────────────────────────────────────────────
    if anomaly:
        send_sms(anomaly_type, data.temperature, data.humidity,
                 data.soil_moisture, tilt)

    return {
        "tilt_angle":       tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":     anomaly_type,
        "send_sms":         anomaly,
    }
