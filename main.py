import os
from fastapi import FastAPI
from pydantic import BaseModel
from twilio.rest import Client

app = FastAPI()

TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")
TWILIO_TO = os.environ.get("TWILIO_TO")

def send_sms(anomaly_type, temperature, soil_moisture, tilt_angle):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=f"SolarYield Alert: {anomaly_type}. Temp: {temperature:.1f}C, Soil: {soil_moisture}. Panel tilted to {tilt_angle} degrees.",
            from_=TWILIO_FROM,
            to=TWILIO_TO
        )
        print("SMS sent successfully")
    except Exception as e:
        print(f"SMS failed: {e}")

class SensorData(BaseModel):
    temperature: float
    humidity: float
    soil_moisture: float
    lux: float
    voltage: float
    current: float
    time_sin: float
    time_cos: float

@app.get("/")
def root():
    return {"status": "SolarYield API running"}

@app.post("/predict")
def predict(data: SensorData):
    tilt = 5
    anomaly = False
    anomaly_type = "none"

    if data.temperature > 35:
        tilt = 25
        anomaly = True
        anomaly_type = "heat_stress"
    elif data.soil_moisture < 1500:
        tilt = 25
        anomaly = True
        anomaly_type = "soil_drought"
    elif data.humidity < 50:
        tilt = 20
        anomaly = True
        anomaly_type = "low_humidity"

    if anomaly:
        send_sms(anomaly_type, data.temperature, data.soil_moisture, tilt)

    return {
        "tilt_angle": tilt,
        "anomaly_detected": anomaly,
        "anomaly_type": anomaly_type,
        "send_sms": anomaly
    }
