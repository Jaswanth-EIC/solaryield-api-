import os
import time
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from twilio.rest import Client

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ─── Twilio credentials from environment variables ────────────────────────────
TWILIO_SID   = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM  = os.environ.get("TWILIO_FROM")
TWILIO_TO    = os.environ.get("TWILIO_TO")

# ─── SMS throttle state ───────────────────────────────────────────────────────
# FIX: Without throttling, a sustained anomaly fires an SMS every 10 seconds,
# burning Twilio credits and spamming the farmer. This dict tracks the last
# send time per anomaly type. Max 1 SMS per anomaly type per hour.
last_sms_time: dict[str, float] = {}
SMS_COOLDOWN_SECONDS = 3600  # 1 hour per anomaly type

# ─── SMS helper ───────────────────────────────────────────────────────────────
def send_sms(anomaly_type: str, temperature: float, humidity: float,
             soil_moisture: float, tilt_angle: int):
    """Send Twilio SMS alert with 1-hour per-anomaly-type throttle."""
    current_time = time.time()
    last_sent    = last_sms_time.get(anomaly_type, 0)

    if current_time - last_sent < SMS_COOLDOWN_SECONDS:
        seconds_remaining = int(SMS_COOLDOWN_SECONDS - (current_time - last_sent))
        logger.info(
            f"SMS throttled for '{anomaly_type}' — "
            f"{seconds_remaining}s until next allowed"
        )
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
    temperature:  float
    humidity:     float
    soil_moisture: float
    lux:          float
    voltage:      float
    current:      float
    time_sin:     float
    time_cos:     float

# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "SolarYield API running"}

# ─── Predict endpoint ─────────────────────────────────────────────────────────
@app.post("/predict")
def predict(data: SensorData):
    tilt         = 5
    anomaly      = False
    anomaly_type = "none"

    # Log incoming data
    logger.info(
        f"Received — Temp: {data.temperature:.1f}C, "
        f"Hum: {data.humidity:.1f}%, "
        f"Soil: {data.soil_moisture}, "
        f"Lux: {data.lux:.1f}, "
        f"V: {data.voltage:.2f}, "
        f"mA: {data.current:.1f}"
    )

    # ── Irradiance gate threshold ──────────────────────────────────────────────
    # NOTE: 5000 lux is a placeholder. Replace with actual 5th percentile
    # of 08:00-18:00 baseline lux readings after 5-day baseline collection.
    LOW_LIGHT_THRESHOLD = 5000  # lux — update after baseline

    # ── Control policy — placeholder threshold logic ───────────────────────────
    # TODO: Replace this entire block with RF model inference after baseline.
    # RF model will be trained in Google Colab, exported as model.pkl,
    # and loaded here via joblib. Residuals exceeding 3σ replace these
    # fixed thresholds with location-specific multivariate anomaly detection.

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

    elif data.lux < 3000 and data.lux > 0:
        # Light deficiency — reduce tilt to allow more irradiance to crop
        tilt         = 0
        anomaly      = True
        anomaly_type = "light_deficiency"

    elif data.voltage < 3.0 and data.lux > LOW_LIGHT_THRESHOLD:
        # Voltage drop but light sufficient — panel suboptimal position
        tilt         = 5
        anomaly      = True
        anomaly_type = "voltage_drop"

    elif data.voltage < 3.0 and data.lux <= LOW_LIGHT_THRESHOLD:
        # Voltage drop due to cloud cover — suppress tilt command (irradiance gate)
        tilt         = 5
        anomaly      = False
        anomaly_type = "irradiance_limited"
        logger.info("Irradiance gate activated — suppressing voltage tilt")

    # ── SMS alert (throttled to max 1 per anomaly type per hour) ──────────────
    if anomaly:
        send_sms(
            anomaly_type,
            data.temperature,
            data.humidity,
            data.soil_moisture,
            tilt
        )

    return {
        "tilt_angle":       tilt,
        "anomaly_detected": anomaly,
        "anomaly_type":     anomaly_type,
        "send_sms":         anomaly
    }
