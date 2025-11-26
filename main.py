# main.py  (MicroPython) — ESP32 edge firmware
# Behavior:
# - reads DHT11, INA219, analog temperature
# - shows summary on OLED each second
# - publishes telemetry to AWS IoT topic sensors/{DEVICE_ID}/telemetry
# - updates Blynk via BlynkManager.send(pin, value)
# - reacts to incoming cloud commands on sensors/{DEVICE_ID}/commands
# - local safety rules (fan on/off, relays off on emergency)
# - polls Blynk for user buttons (stop price, relay overrides)

import time
import ujson
import urequests
import machine

# Components (use your filenames uploaded in Components/)
from Components.dht11 import DHT11Sensor
from Components.ina_curent_sensor import INA219
from Components.analog_temperature_sensor import AnalogTempSensor
from Components.dual_channel_relay import DualRelay
from Components.Fan import DCFan
from Components.buzzer import Buzzer
from Components.ssd1306 import SSD1306_I2C
from AWSmanager.aws_iot import AWSIoTClient
from AWSmanager.blynk_manager import BlynkManager
from machine import Pin, I2C

# ---------------- USER CONFIG ----------------
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"
DEVICE_ID = "esp32-sim-01"

# AWS IoT endpoint (replace with your actual ATS endpoint)
IOT_ENDPOINT = "a2l0qvmme084mx-ats.iot.us-east-1.amazonaws.com"

# Blynk token (put your token)
BLYNK_TOKEN = "YOUR_BLYNK_TOKEN"

# pins (adjust if your wiring differs)
DHT_PIN = 14
INA_SDA = 21
INA_SCL = 22
ANALOG_PIN = 35
RELAY1_CH1 = 26
RELAY1_CH2 = 27
RELAY2_CH1 = 32
RELAY2_CH2 = 33
FAN_RELAY_PIN = 25
BUZZER_PIN = 13
I2C_SDA = 21
I2C_SCL = 22

# thresholds
TEMP_FAN_ON = 45.0   # analog temp -> fan on
TEMP_FAN_OFF = 38.0  # analog temp -> fan off
DHT_TEMP_SHUTOFF = 60.0   # emergency shutdown if DHT exhibits extreme temp
VOLTAGE_OVER_THRESHOLD = 14.0  # example; set to your system spec
CURRENT_OVERLOAD_MA = 2000  # mA

# Blynk virtual mapping
V = {
    'dht_temp': 1, 'dht_hum': 2, 'analog_temp': 3,
    'ina_v': 4, 'ina_i': 5, 'ina_p': 6, 'price': 12,
    'fan': 11, 'warning': 18, 'loc_temp': 19, 'loc_hum': 20,
    'stop_price_button': 21,
    'relay1_override': 22, 'relay2_override': 23, 'relay3_override': 24, 'relay4_override': 25
}

# -------------------------------------------

# ---------- network connect ----------
wlan = machine.Pin  # placeholder to avoid linter errors
try:
    import network
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    if not wifi.isconnected():
        print("Connecting to WiFi...")
        wifi.connect(WIFI_SSID, WIFI_PASS)
        t0 = time.time()
        while not wifi.isconnected() and time.time() - t0 < 15:
            time.sleep(1)
    print("WiFi:", wifi.ifconfig())
except Exception as e:
    print("WiFi init error:", e)

# ---------- init hardware ----------
dht = DHT11Sensor(DHT_PIN)
ina = INA219(sda_pin=INA_SDA, scl_pin=INA_SCL)
ina.configure()  # use default calibration; tune if needed
analog_temp = AnalogTempSensor(pin=ANALOG_PIN, sensor_type='lm35')
relays_1 = DualRelay(RELAY1_CH1, RELAY1_CH2, active_high=True)
relays_2 = DualRelay(RELAY2_CH1, RELAY2_CH2, active_high=True)
fan = DCFan(FAN_RELAY_PIN, active_high=True)
buzzer = Buzzer(BUZZER_PIN, active_high=True)

# OLED setup (I2C)
i2c = I2C(0, scl=machine.Pin(I2C_SCL), sda=machine.Pin(I2C_SDA), freq=400000)
oled = SSD1306_I2C(128, 32, i2c)  # use 32 or 64 height accordingly

# Blynk manager (MicroPython helper)
blynk = BlynkManager(BLYNK_TOKEN, WIFI_SSID, WIFI_PASS)

# AWS IoT client using your AWSmanager implementation (mutual TLS)
def mqtt_message_callback(topic, msg):
    """Called by AWS IoT client when a message is received on subscribed topic."""
    try:
        t = topic.decode() if isinstance(topic, bytes) else topic
        payload_raw = msg.decode() if isinstance(msg, bytes) else msg
        print("MQTT in:", t, payload_raw)
        data = ujson.loads(payload_raw)
    except Exception as e:
        print("MQTT parse error:", e)
        return

    # expected command messages: {"cmd":"relays_off"} or {"cmd":"fan_on"} or {"cmd":"beep":2, "text":"..."}
    cmd = data.get("cmd")
    if cmd == "relays_off" or cmd == "shutdown":
        relays_1.all_off()
        relays_2.all_off()
        fan.on()
        oled.fill(0)
        oled.text("CLOUD SHUTDOWN", 0, 0)
        oled.show()
        buzzer.beep(times=3)
    elif cmd == "fan_on":
        fan.on()
        oled.fill(0)
        oled.text("FAN ON (CLOUD)", 0, 0)
        oled.show()
    elif cmd == "fan_off":
        fan.off()
    elif cmd == "beep":
        times = int(data.get("times", 1))
        buzzer.beep(times=times)
    elif cmd == "warning":
        txt = data.get("text", "Warning")
        # show on oled briefly and beep twice
        oled.fill(0)
        oled.text("WARN:", 0, 0)
        oled.text(txt[:16], 0, 10)
        oled.show()
        buzzer.beep(times=2)
    # add additional commands or relay toggles as needed

# create MQTT client and subscribe to command topic
iot_client = AWSIoTClient(client_id=DEVICE_ID, server=IOT_ENDPOINT,
                          certfile="/certs/cert.pem.crt", keyfile="/certs/private.pem.key",
                          cafile="/certs/root-CA.pem")
try:
    iot_client.connect(subs=[("sensors/{}/commands".format(DEVICE_ID), 1)], msg_callback=mqtt_message_callback)
    print("Connected to AWS IoT")
except Exception as e:
    print("AWS IoT connect error:", e)

# helper: read virtual pin from Blynk (GET)
def blynk_get(pin):
    try:
        url = "https://blynk.cloud/external/api/get?token={}&V{}".format(BLYNK_TOKEN, pin)
        r = urequests.get(url, timeout=5)
        arr = r.json()
        r.close()
        if isinstance(arr, list):
            return arr[0]
        return arr
    except Exception as e:
        # read error
        return None

# helper: publish telemetry to AWS (topic)
def publish_telemetry(payload):
    try:
        # ensure plain JSON (MicroPython doesn't like Decimal)
        iot_client.publish("sensors/{}/telemetry".format(DEVICE_ID), payload, qos=1)
        return True
    except Exception as e:
        print("Publish error:", e)
        return False

# main loop
price_recording = True
price_acc = 0.0
RATE_PER_KWH = 6.50  # currency unit / kWh (adjust)

print("Starting main loop (1 Hz)...")
while True:
    try:
        # read sensors
        dht_read = dht.read() or {'temperature': None, 'humidity': None}
        analog_t = analog_temp.read_temperature()
        shunt_v, bus_v, current_a, power_w = ina.read_all()
        current_mA = round(current_a * 1000, 2)
        power_mW = round(power_w * 1000, 2)

        # read blynk stop-price button and relay override buttons
        stop_price_val = blynk_get(V['stop_price_button'])
        if stop_price_val is not None:
            # blynk returns "1" or "0" usually as strings
            if str(stop_price_val) == "1":
                price_recording = False
            else:
                price_recording = True

        # read relay override pins
        for idx, pin in enumerate([V['relay1_override'], V['relay2_override'], V['relay3_override'], V['relay4_override']]):
            val = blynk_get(pin)
            if val is None:
                continue
            try:
                v = int(val)
            except:
                v = 0
            # map idx to specific relay channel
            if idx == 0:
                # relay1 channel 1
                if v == 1:
                    relays_1.on(1)
                else:
                    relays_1.off(1)
            elif idx == 1:
                if v == 1:
                    relays_1.on(2)
                else:
                    relays_1.off(2)
            elif idx == 2:
                if v == 1:
                    relays_2.on(1)
                else:
                    relays_2.off(1)
            elif idx == 3:
                if v == 1:
                    relays_2.on(2)
                else:
                    relays_2.off(2)

        # price accumulation (if enabled)
        if price_recording:
            # power_w is watts; energy for 1 second = power_w * (1/3600) Wh; cost = energy_kWh * rate
            energy_kwh = (power_w / 1000.0) * (1.0 / 3600.0)
            price_acc += energy_kwh * RATE_PER_KWH

        # local safety checks
        if analog_t is not None:
            if analog_t >= TEMP_FAN_ON:
                fan.on()
                oled.fill(0)
                oled.text("Analog TEMP HIGH", 0, 0)
                oled.text("%.1fC Fan ON" % (analog_t), 0, 10)
                oled.show()
                buzzer.beep(times=2)
            elif analog_t <= TEMP_FAN_OFF:
                fan.off()

        dht_t = dht_read.get('temperature')
        if dht_t is not None and dht_t >= DHT_TEMP_SHUTOFF:
            # emergency: switch off relays
            relays_1.all_off()
            relays_2.all_off()
            oled.fill(0)
            oled.text("EMERGENCY: DHT T", 0, 0)
            oled.text("%.1fC SHUTDN" % (dht_t), 0, 10)
            oled.show()
            buzzer.beep(times=4)

        if bus_v is not None and bus_v >= VOLTAGE_OVER_THRESHOLD:
            relays_1.all_off()
            relays_2.all_off()
            fan.on()
            oled.fill(0)
            oled.text("OVERVOLTAGE!", 0, 0)
            oled.text("%.2fV" % (bus_v), 0, 10)
            oled.show()
            buzzer.beep(times=3)

        if current_mA is not None and current_mA >= CURRENT_OVERLOAD_MA:
            relays_1.all_off()
            relays_2.all_off()
            oled.fill(0)
            oled.text("OVERCURRENT!", 0, 0)
            oled.text("%dmA" % (current_mA), 0, 10)
            oled.show()
            buzzer.beep(times=3)

        # compose telemetry payload (simple dict -> AWSmanager will stringify)
        telemetry = {
            "device_id": DEVICE_ID,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "DHT11_Temperature": dht_read.get('temperature'),
            "DHT11_Humidity": dht_read.get('humidity'),
            "Analog_Temperature": analog_t,
            "INA219_Voltage(V)": round(bus_v, 3) if bus_v is not None else None,
            "INA219_Current(mA)": current_mA,
            "INA219_Power(mW)": power_mW,
            "Price_Rs": round(price_acc, 4),
            "Relay_1": relays_1.state(1),
            "Relay_2": relays_1.state(2),
            "Relay_3": relays_2.state(1),
            "Relay_4": relays_2.state(2),
            "DC_Fan": fan.state(),
            "Warning": None
        }

        # publish telemetry
        publish_telemetry(telemetry)

        # push a few values to Blynk (non-blocking best-effort)
        try:
            blynk.send(V['dht_temp'], telemetry["DHT11_Temperature"] or 0)
            blynk.send(V['dht_hum'], telemetry["DHT11_Humidity"] or 0)
            blynk.send(V['ina_v'], telemetry["INA219_Voltage(V)"] or 0)
            blynk.send(V['ina_i'], telemetry["INA219_Current(mA)"] or 0)
            blynk.send(V['price'], telemetry["Price_Rs"] or 0)
        except Exception as e:
            print("Blynk send error:", e)

        # OLED status snapshot
        oled.fill(0)
        oled.text("T: %sC H:%s%%" % (str(telemetry["DHT11_Temperature"] or "NA"), str(telemetry["DHT11_Humidity"] or "NA")), 0, 0)
        oled.text("V:%s I:%s" % (str(telemetry["INA219_Voltage(V)"] or "NA"), str(telemetry["INA219_Current(mA)"] or "NA")), 0, 10)
        oled.text("Fan:%s Price:%.2f" % (fan.state(), price_acc), 0, 20)
        oled.show()

    except Exception as e:
        print("Main loop error:", e)

    # check for incoming mqtt commands (non-blocking)
    try:
        iot_client.check_msg()
    except Exception as e:
        pass

    time.sleep(1)
