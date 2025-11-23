import json
import time
import random
import requests
import boto3
from datetime import datetime

# --- CONFIGURATION ---
AWS_REGION = "us-east-1"
AWS_IOT_ENDPOINT = "a1p2b3c4d5e6f7-ats.iot.us-east-1.amazonaws.com"
THING_NAME = "esp32-grid-01"
MQTT_TOPIC = f"sensors/{THING_NAME}/telemetry"
PUBLISH_INTERVAL = 5  # seconds

BLYNK_TOKEN = "3sdYNvxGnXYrPsAtMv1OemLkLHPHUsFY"
BLYNK_BASE_URL = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}"

# Initialize AWS IoT Data client
iot_client = boto3.client("iot-data", region_name=AWS_REGION, endpoint_url=f"https://{AWS_IOT_ENDPOINT}")

def make_safe_value(base, variation, minimum, maximum):
    val = base + random.uniform(-variation, variation)
    val = max(minimum, min(maximum, val))
    return round(val, 2)

def publish_to_aws(payload):
    try:
        response = iot_client.publish(
            topic=MQTT_TOPIC,
            qos=1,
            payload=json.dumps(payload)
        )
        print(f"Published to AWS IoT: {payload}")
    except Exception as e:
        print(f"Failed to publish to AWS IoT: {e}")

def update_blynk(pin, value):
    try:
        url = f"{BLYNK_BASE_URL}&V{pin}={value}"
        resp = requests.get(url, timeout=5)
        print(f"Blynk pin V{pin} updated to {value} (status {resp.status_code})")
    except Exception as e:
        print(f"Failed to update Blynk: {e}")

def generate_dummy_payload():
    # Generating valid dummy data within safe ranges (avoid thresholds)
    dht_temperature = make_safe_value(28.0, 4.0, 24.0, 34.0)   # °C (24-34 safe)
    dht_humidity = make_safe_value(60.0, 10.0, 40.0, 70.0)      # % (40-70 safe)
    analog_temperature = make_safe_value(30.0, 5.0, 25.0, 40.0) # °C (25-40 safe)
    ina_voltage = make_safe_value(12.0, 0.5, 11.0, 12.7)        # Volts (11-12.7 safe)
    ina_current = make_safe_value(500, 200, 100, 1400)           # mA (100-1400 safe)
    ina_power = round(ina_voltage * ina_current / 1000.0 * 1000, 2) # mW

    # Location weather from OpenWeather dummy similar but moderate
    location_temperature = make_safe_value(30.0, 5.0, 20.0, 35.0)  # °C
    location_humidity = make_safe_value(65.0, 15.0, 40.0, 80.0)    # %

    return {
        "device_id": THING_NAME,
        "ts": datetime.utcnow().isoformat() + "Z",
        "DHT11_Temperature": dht_temperature,
        "DHT11_Humidity": dht_humidity,
        "Analog_Temperature": analog_temperature,
        "INA219_1_Voltage(V)": ina_voltage,
        "INA219_1_current(mA)": ina_current,
        "INA219_1_Power(mW)": ina_power,
        "Location_Temperature": location_temperature,
        "Location_Humidity": location_humidity,
    }

def main():
    while True:
        payload = generate_dummy_payload()
        publish_to_aws(payload)

        # Update Blynk virtual pins accordingly
        update_blynk(1, payload["DHT11_Temperature"])
        update_blynk(2, payload["DHT11_Humidity"])
        update_blynk(3, payload["Analog_Temperature"])
        update_blynk(4, payload["INA219_1_Voltage(V)"])
        update_blynk(5, payload["INA219_1_current(mA)"])
        update_blynk(6, payload["INA219_1_Power(mW)"])
        update_blynk(19, payload["Location_Temperature"])
        update_blynk(20, payload["Location_Humidity"])

        time.sleep(PUBLISH_INTERVAL)

if __name__ == "__main__":
    main()
