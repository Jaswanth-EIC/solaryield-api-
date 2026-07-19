import os
import time
import json
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import deque
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from twilio.rest import Client
import io
import csv

# ─── Try to load RF model bundle ─────────────────────────────────────────────
# If model_bundle.pkl exists, use RF model
# If not, fall back to threshold logic automatically
RF_MODEL_AVAILABLE = False
model_bundle = None

try:
    import joblib
    if os.path.exists("model_bundle.pkl"):
        model_bundle = joblib.load("model_bundle.pkl")
        RF_MODEL_AVAILABLE = True
        logging.info("RF model bundle loaded successfully")
    else:
        logging.info("model_bundle.pkl not found — using threshold fallback")
except Exception as e:
    logging.error(f"Failed to load RF model: {e}")

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

# ─── Mode control password ─────────────────────────────────────────────────────
MODE_PASSWORD = os.environ.get("MODE_PASSWORD")
# Set this in Render's environment variables, same place as TWILIO_SID.
# Never hardcode it here — this file is in a public repo.

# ─── SMS state ────────────────────────────────────────────────────────────────
previous_anomaly_state: dict[str, bool] = {}

# ─── Friendly, non-technical labels for SMS (no jargon, no degree symbols) ────
FRIENDLY_LABELS = {
    "heat_stress":          "Heat stress",
    "low_humidity":         "Low humidity",
    "light_deficiency":     "Low light",
    "soil_drought":         "Dry soil",
    "voltage_drop":         "Low power",
    "multivariate_anomaly": "Unusual conditions",
    "temp_anomaly_low":     "Unusual conditions",
}

def friendly_label(anomaly_type: str) -> str:
    return FRIENDLY_LABELS.get(anomaly_type, anomaly_type.replace("_", " ").title())

# ─── Persistent log ───────────────────────────────────────────────────────────
LOG_BUFFER_SIZE = 8640
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

# ─── Google Sheets logging ────────────────────────────────────────────────────
SHEETS_URL = "https://script.google.com/macros/s/AKfycbw2L8MJmkXec7YuZj-H6koqexwdpx66JwFZMx5ZPtqRf-HwCb37dgoUjpD8ZWtT6apE/exec"

def log_to_sheets(entry: dict):
    try:
        import urllib.request
        data = json.dumps(entry).encode("utf-8")
        req  = urllib.request.Request(
            SHEETS_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error(f"Google Sheets logging failed: {e}")

# ─── SMS helper ───────────────────────────────────────────────────────────────
def send_sms(body: str):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=body, from_=TWILIO_FROM, to=TWILIO_TO)
        logger.info(f"SMS sent: {body[:60]}...")
    except Exception as e:
        logger.error(f"SMS failed: {e}")

def handle_sms(anomaly_type, anomaly, temperature, humidity, soil_moisture, tilt_angle):
    was_anomaly = previous_anomaly_state.get(anomaly_type, False)
    if anomaly and not was_anomaly:
        label = friendly_label(anomaly_type)
        send_sms(
            f"SolarYield: {label} detected. Panel auto-tilted to protect your crops."
        )
        previous_anomaly_state[anomaly_type] = True
    elif not anomaly and was_anomaly:
        label = friendly_label(anomaly_type)
        send_sms(
            f"SolarYield: {label} resolved. Panel returned to normal position."
        )
        previous_anomaly_state[anomaly_type] = False

# ─── RF anomaly detection ─────────────────────────────────────────────────────
def rf_predict(data) -> tuple[int, bool, str]:
    """
    Run RF residual-based anomaly detection.
    Returns (tilt_angle, anomaly_detected, anomaly_type)
    """
    bundle = model_bundle
    rf_models      = bundle['rf_models']
    thresholds     = bundle['thresholds']
    target_sensors = bundle['target_sensors']
    irradiance_gate = bundle['irradiance_gate']

    sensor_values = {
        'temperature':  data.temperature,
        'humidity':     data.humidity,
        'lux':          data.lux,
        'time_sin':     data.time_sin,
        'time_cos':     data.time_cos,
    }

    anomalies_detected = {}

    for sensor in target_sensors:
        rf         = rf_models[sensor]['model']
        feat_cols  = rf_models[sensor]['features']
        X          = np.array([[sensor_values[f] for f in feat_cols]])
        predicted  = rf.predict(X)[0]
        actual     = sensor_values[sensor]
        residual   = actual - predicted
        t          = thresholds[sensor]

        if residual > t['upper_3sigma'] or residual < t['lower_3sigma']:
            anomalies_detected[sensor] = residual

    # ── Daytime gate — suppress lux anomaly at night ──────────────────────────
    sg_hour = datetime.now(timezone(timedelta(hours=8))).hour
    is_daytime = 7 <= sg_hour <= 19
    if 'lux' in anomalies_detected and not is_daytime:
        del anomalies_detected['lux']

    # ── Irradiance gate — suppress voltage anomaly in low light ───────────────
    # (voltage not in RF model yet — handled in threshold layer below)

    if not anomalies_detected:
        return 5, False, "none"

    # ── Two-layer control policy ──────────────────────────────────────────────
    # Priority: soil_drought > heat_stress > light_deficiency > voltage_drop
    if 'temperature' in anomalies_detected and anomalies_detected['temperature'] > 0:
        return 25, True, "heat_stress"
    if 'humidity' in anomalies_detected and anomalies_detected['humidity'] < 0:
        return 20, True, "low_humidity"
    if 'lux' in anomalies_detected and anomalies_detected['lux'] < 0:
        # Light below expected — reduce tilt to let more light through
        if data.lux < irradiance_gate:
            return 5, False, "irradiance_limited"
        return 0, True, "light_deficiency"
    if 'temperature' in anomalies_detected and anomalies_detected['temperature'] < 0:
        # Temperature anomaly low — unusual, log but no tilt
        return 5, True, "temp_anomaly_low"

    return 5, True, "multivariate_anomaly"


# ─── Threshold fallback ───────────────────────────────────────────────────────
def threshold_predict(data) -> tuple[int, bool, str]:
    sg_hour    = datetime.now(timezone(timedelta(hours=8))).hour
    is_daytime = 7 <= sg_hour <= 19
    LOW_LIGHT_THRESHOLD = model_bundle['irradiance_gate'] if model_bundle else 5000

    if data.temperature > 35:
        return 25, True, "heat_stress"
    elif data.soil_moisture < 1500:
        return 25, True, "soil_drought"
    elif data.humidity < 50:
        return 20, True, "low_humidity"
    elif 0 < data.lux < 3000 and is_daytime:
        return 0, True, "light_deficiency"
    elif data.voltage < 3.0 and data.lux > LOW_LIGHT_THRESHOLD:
        return 5, True, "voltage_drop"
    elif data.voltage < 3.0 and data.lux <= LOW_LIGHT_THRESHOLD:
        logger.info("Irradiance gate activated")
        return 5, False, "irradiance_limited"
    return 5, False, "none"

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

# ─── Mode state (auto / manual override) ───────────────────────────────────────
MODE_FILE = "mode_state.json"
mode_state = {"mode": "auto", "manual_tilt_angle": 5}

def load_mode_from_disk():
    if os.path.exists(MODE_FILE):
        try:
            with open(MODE_FILE, "r") as f:
                mode_state.update(json.load(f))
            logger.info(f"Loaded mode state: {mode_state}")
        except Exception as e:
            logger.error(f"Failed to load mode state: {e}")

def save_mode_to_disk():
    try:
        with open(MODE_FILE, "w") as f:
            json.dump(mode_state, f)
    except Exception as e:
        logger.error(f"Failed to save mode state: {e}")

load_mode_from_disk()

class ModeUpdate(BaseModel):
    mode: str
    manual_tilt_angle: int = 5
    password: str

@app.get("/mode")
def get_mode():
    return mode_state

@app.post("/mode")
def set_mode(update: ModeUpdate):
    if not MODE_PASSWORD:
        return JSONResponse(status_code=500, content={"error": "MODE_PASSWORD not configured on server"})
    if update.password != MODE_PASSWORD:
        return JSONResponse(status_code=401, content={"error": "Incorrect password"})
    if update.mode not in ("auto", "manual"):
        return JSONResponse(status_code=400, content={"error": "mode must be 'auto' or 'manual'"})
    mode_state["mode"] = update.mode
    mode_state["manual_tilt_angle"] = max(0, min(30, update.manual_tilt_angle))
    save_mode_to_disk()
    logger.info(f"Mode changed to {mode_state}")
    return mode_state

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
    return {
        "status": "SolarYield API running",
        "log_entries": len(reading_log),
        "rf_model": "loaded" if RF_MODEL_AVAILABLE else "threshold fallback",
    }

# ─── Log endpoint ─────────────────────────────────────────────────────────────
@app.get("/log")
def get_log(n: int = 360):
    n = min(n, LOG_BUFFER_SIZE)
    return {"count": len(reading_log), "readings": list(reading_log)[-n:]}

# ─── CSV export ───────────────────────────────────────────────────────────────
@app.get("/export")
def export_csv():
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

# ─── Clear log ────────────────────────────────────────────────────────────────
@app.delete("/clear-log")
def clear_log():
    reading_log.clear()
    save_log_to_disk()
    return {"status": "log cleared", "entries_remaining": 0}

# ─── Predict endpoint ─────────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SensorData):
    logger.info(
        f"Temp: {data.temperature:.1f}C, Hum: {data.humidity:.1f}%, "
        f"Soil: {data.soil_moisture}, Lux: {data.lux:.1f}, "
        f"V: {data.voltage:.2f}, mA: {data.current:.1f}"
    )

    # ── Manual override takes priority over RF/threshold ──────────────────────
    if mode_state["mode"] == "manual":
        tilt = mode_state["manual_tilt_angle"]
        anomaly = False
        anomaly_type = "manual"
        controller = "manual"
    elif RF_MODEL_AVAILABLE:
        tilt, anomaly, anomaly_type = rf_predict(data)
        controller = "RF"
    else:
        tilt, anomaly, anomaly_type = threshold_predict(data)
        controller = "threshold"

    logger.info(f"[{controller}] {anomaly_type} → tilt {tilt}°")

    # ── SMS ───────────────────────────────────────────────────────────────────
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
        "controller":       controller,
    }
    reading_log.append(log_entry)

    # Save to disk every 60 readings
    if len(reading_log) % 60 == 0:
        save_log_to_disk()

    # Log to Google Sheets
    log_to_sheets(log_entry)

    return {
        "tilt_angle":       tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":     anomaly_type,
        "send_sms":         anomaly,
        "controller":       controller,
    }
