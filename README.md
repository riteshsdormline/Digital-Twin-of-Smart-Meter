# Intelligent Energy Management — Digital Twin of Smart Meter

A Digital Twin–driven smart metering prototype implementing human-centric, Industry 5.0 principles. This project demonstrates a working prototype that collects real-time telemetry (current, voltage, temperature, humidity) using an ESP32-based edge device (MicroPython), publishes secure telemetry to AWS IoT Core, stores telemetry in DynamoDB, and runs serverless predictive analytics (AWS Lambda) to enable automated safety actions and human-friendly dashboards (OLED / Blynk).

Reference / background:
Smart Blind Stick for Visually Impaired Navigation — IEEE article (for context)
https://ieeexplore.ieee.org/document/11386629

(Primary paper for this repository:)
Intelligent Energy Management Using Digital Twin–Driven Smart Metering in Industry 5.0 — see manuscript and references in repository.

## Short description

This repository contains code, schematics, and documentation to implement a digital twin of a smart meter supporting an EV charging/grid demonstration. The system integrates:

- Edge telemetry: ESP32 (MicroPython) + INA219 (current/voltage), DHT11 (temperature/humidity), analogue temperature sensor, OLED, relays, buzzer.
- Cloud backend: AWS IoT Core (MQTT/TLS with X.509), Lambda functions for analytics/prediction, DynamoDB for telemetry storage.
- Human interfaces: I2C OLED display for local feedback and Blynk dashboard/mobile for remote monitoring & control.
- Safety & autonomy: Local fail-safe rules on ESP32 and cloud-driven predictive alerts that send commands back to the edge.

Language composition: Python (MicroPython and Python scripts/tools).

## Features

- Real-time telemetry (1 Hz) from edge sensors.
- Secure device authentication (X.509 certificates, MQTT over TLS).
- Local safety protocols (overcurrent, over-temperature) with immediate relay/fan/buzzer actions.
- Cloud analytics (Lambda) for lightweight regression-based forecasting and anomaly detection.
- Human-friendly dashboards: OLED + Blynk for non-technical users.
- Digital twin concept: live sync of physical asset telemetry with cloud model for simulation and safe testing.

## Hardware (prototype)

- ESP32 microcontroller (MicroPython firmware)
- INA219 current/voltage sensor (I2C)
- DHT11 (temperature & humidity)
- NTC analogue temperature sensor (or LM35)
- I2C OLED display
- 5V relay modules (dual-channel)
- Buzzer, DC cooling fan
- 18650 battery pack with BMS (3S example in prototype)
- Solar panel / SMPS (20 W example) for hybrid charging demonstration
- Charging modules / CN3065-based charging board (for test setup)

See the `Figures/` directory (if available) for prototype photos and circuit diagrams.

## Software architecture

Edge (ESP32, MicroPython)
- Reads sensors (INA219, DHT11, analog temp).
- Enforces local safety thresholds and immediate actions (relay off, fan on, buzzer).
- Publishes JSON telemetry to AWS IoT Core via MQTT/TLS.
- Receives commands from cloud to execute safety actions or change thresholds.
- Provides local visualization on an OLED.

Cloud (AWS)
- AWS IoT Core: device gateway and rule engine.
- DynamoDB: telemetry storage.
- AWS Lambda: lightweight regression/anomaly detection, forecasts, and decisioning.
- Optional: SNS or other notification channels for alerts.

Dashboard
- Blynk dashboard (or similar) for real-time remote viewing and manual overrides.

## start (overview)

1. Flash MicroPython on ESP32
   - Download the latest MicroPython firmware for ESP32.
   - Use esptool to flash firmware to your device.

2. Provision sensors and wiring
   - Wire INA219 to ESP32 I2C (SDA, SCL).
   - Wire DHT11 to a digital pin.
   - Wire analog temp sensor to ADC pin.
   - Wire OLED to I2C bus.
   - Wire relays and buzzer to GPIOs with appropriate driver circuitry.

3. Configure AWS IoT
   - Create a Thing in AWS IoT Core.
   - Generate an X.509 certificate and attach the policy allowing required publish/subscribe and IoT actions.
   - Configure IoT rule(s) to forward telemetry to DynamoDB and trigger Lambda functions.

4. Deploy Lambda analytics
   - Create Lambda functions for regression-based forecasting and anomaly detection.
   - Configure Lambda to run on IoT rule triggers and write predictions or actions back to IoT topics.

5. Deploy edge scripts
   - Copy the MicroPython scripts under `edge/` (or `esp32/`) to the ESP32 using ampy/rshell or an IDE.
   - Provide the device with Wi-Fi credentials and AWS endpoint/certificates (or use an MQTT proxy).

6. Start the system
   - Power the prototype and verify local OLED updates.
   - Confirm telemetry is published to AWS IoT Core and appears in DynamoDB.
   - Test local fail-safe thresholds and cloud-triggered commands.
7. Blynk Dashboard
   - Retrieve data and control ESP32 action.
   - Get error notice on Terminal screen on issue.

## Repository layout (suggested)

- README.md — this file
- edge/ or esp32/ — MicroPython source code for ESP32
- cloud/ — example Lambda functions and AWS deployment scripts
- scripts/ — Python utilities (data plotting, telemetry replay, local analysis)
- requirements.txt — Python dependencies for cloud/local scripts
- LICENSE
- references.bib or references.md

## Example telemetry payload (JSON)
{
  "device_id": "esp32-001",
  "timestamp": "2026-03-16T12:00:00Z",
  "voltage_v": 12.34,
  "current_a": 1.23,
  "power_w": 15.19,
  "battery_temp_c": 34.5,
  "ambient_temp_c": 28.2,
  "humidity_pct": 58.1
}

## Safety & local failure protocols (examples)

- If measured battery temperature > 45°C -> activate cooling fan, sound buzzer, disable charging relay.
- If measured voltage > safety threshold -> disconnect charger relay immediately.
- If measured current > overload limit -> switch off relays and notify cloud.
- Telemetry is locally buffered and re-sent when connectivity is restored.

## Predictive analytics (cloud)

- Lambda functions implement a lightweight regression-based forecasting model (example: linear regression on recent windows) to predict short-term spikes and issue preemptive actions.
- OpenWeather API may be used for context-aware risk-scoring (e.g., rain prediction vs solar generation).
- Predictions and anomaly scores stored alongside raw telemetry for auditing.

## Notes about security

- Use mutual TLS (X.509 certs) for device authentication.
- Use IAM least-privilege for Lambda and IoT policies.
- Revoke certificates if a device is compromised; track device identities.

## Testing and results

- The prototype logs battery metrics and runs forecasting over a short window (example: next 10 minutes).
- When thresholds or predicted values exceed safe levels, local actions are taken and alerts issued to the dashboard/owner.
- Expected telemetry latency to DynamoDB via IoT Core + Lambda: ~1–2 seconds (depending on network).
