import time, ujson, machine, network, urequests

# --- Fill THESE for your setup ---
WIFI_SSID = "vivo T3x 5G"
WIFI_PASS = "VVTX3333"
CLIENT_ID = "esp32-grid-01"
AWS_ENDPOINT = "a1kpv2cv7730x1-ats.iot.us-east-1.amazonaws.com"
PUB_TOPIC = f"sensors/{CLIENT_ID}/telemetry"
SUB_TOPIC = f"sensors/{CLIENT_ID}/commands"
BLYNK_TOKEN = "3sdYNvxGnXYrPsAtMv1OemLkLHPHUsFY"
BLYNK_API = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}"
OPENWEATHER_API_KEY = "c3f17fb0df21e94913a0ba7300139dc8"
LAT, LON = "28.6139", "77.2090"   # DELHI; replace as needed

# --- Pins and Driver Imports ---
from Components.dht11 import DHT11Sensor
from Components.ina_curent_sensor import INA219
from Components.analog_temperature_sensor import AnalogTempSensor
from Components.dual_channel_relay import DualRelay
from Components.buzzer import Buzzer
from AWSmanager.aws_iot import AWSIoTClient

try:
    from ssd1306 import SSD1306_I2C
except ImportError:
    print("SSD1306 OLED driver missing!")
    SSD1306_I2C = None

DHT_PIN = 14
ANALOG_PIN = 35
INA_SDA, INA_SCL = 21, 22
RELAY1_CH1, RELAY1_CH2 = 26, 27
RELAY2_CH1, RELAY2_CH2 = 32, 33
FAN_RELAY_CH, FAN_IS_ON_RELAY_BANK = 1, 1
BUZZER_PIN = 15
OLED_SDA, OLED_SCL, OLED_WIDTH, OLED_HEIGHT = 21, 22, 128, 32

PUBLISH_INTERVAL = 30
TEMP_THRESHOLD_FAN_ON = 50.0
CURRENT_OVERLOAD_MA = 1500.0

# --- WiFi Setup ---
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
def connect_wifi(timeout=20):
    if wifi.isconnected():
        return True
    wifi.connect(WIFI_SSID, WIFI_PASS)
    t0 = time.time()
    while not wifi.isconnected() and time.time()-t0 < timeout:
        time.sleep(1)
    return wifi.isconnected()
connect_wifi()

# --- Device Init ---
dht = DHT11Sensor(DHT_PIN)
ina = INA219(sda_pin=INA_SDA, scl_pin=INA_SCL)
ina.configure()
analog = AnalogTempSensor(ANALOG_PIN, sensor_type="lm35")
relay1 = DualRelay(RELAY1_CH1, RELAY1_CH2, active_high=True)
relay2 = DualRelay(RELAY2_CH1, RELAY2_CH2, active_high=True)
buzzer = Buzzer(BUZZER_PIN)

oled = None
if SSD1306_I2C:
    try:
        i2c = machine.I2C(0, scl=machine.Pin(OLED_SCL), sda=machine.Pin(OLED_SDA))
        oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
    except Exception as e:
        print("OLED error:", e)
# --- Helper funcs ---
def fan_on(): relay1.on(FAN_RELAY_CH) if FAN_IS_ON_RELAY_BANK==1 else relay2.on(FAN_RELAY_CH)
def fan_off(): relay1.off(FAN_RELAY_CH) if FAN_IS_ON_RELAY_BANK==1 else relay2.off(FAN_RELAY_CH)

def blynk_update(pin, value):
    try:
        urequests.get(f"{BLYNK_API}&V{pin}={value}", timeout=4).close()
    except: pass

def get_weather():
    try:
        url = (f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}"
               f"&appid={OPENWEATHER_API_KEY}&units=metric")
        resp = urequests.get(url)
        d = resp.json()
        resp.close()
        return {
            "temperature": d["main"]["temp"],
            "humidity": d["main"]["humidity"],
            "desc": d["weather"][0]["description"].upper()
        }
    except Exception as e:
        print("Weather API fail:", e)
        return {"temperature": None, "humidity": None, "desc": "ERR"}

def make_payload(weather):
    try: d = dht.read() or {}
    except: d = {}
    try: analog_t = analog.read_temperature()
    except: analog_t = None
    try: _, bus_v, current_a, power_w = ina.read_all()
    except: bus_v, current_a, power_w = 0, 0, 0
    return {
        "device_id": CLIENT_ID,
        "ts": time.time(),
        "DHT11_Temperature": d.get("temperature"),
        "DHT11_Humidity": d.get("humidity"),
        "Analog_Temperature": analog_t,
        "INA219_1_Voltage(V)": round(bus_v,3),
        "INA219_1_current(mA)": round(current_a*1000,2),
        "INA219_1_Power(mW)": round(power_w*1000,2),
        "Location_Temperature": weather["temperature"],
        "Location_Humidity": weather["humidity"],
        "Weather_Desc": weather["desc"]
    }

def update_blynk(payload):
    blynk_update(1, payload.get("DHT11_Temperature") or "")
    blynk_update(2, payload.get("DHT11_Humidity") or "")
    blynk_update(3, payload.get("Analog_Temperature") or "")
    blynk_update(4, payload.get("INA219_1_Voltage(V)") or "")
    blynk_update(5, payload.get("INA219_1_current(mA)") or "")
    blynk_update(6, payload.get("INA219_1_Power(mW)") or "")
    blynk_update(19, payload.get("Location_Temperature") or "")
    blynk_update(20, payload.get("Location_Humidity") or "")

mqtt = AWSIoTClient(client_id=CLIENT_ID, server=AWS_ENDPOINT,
    certfile="/cert.pem.crt", keyfile="/private.pem.key", cafile="/AmazonRootCA1.pem")

def mqtt_connect():
    try:
        mqtt.connect(subs=[(SUB_TOPIC, 1)], msg_callback=None)
        return True
    except: return False
while not mqtt_connect(): time.sleep(5)

# --- Main loop ---
while True:
    try:
        if not wifi.isconnected(): connect_wifi()
        weather = get_weather()
        payload = make_payload(weather)

        #--- Local (fail-safe) fan control ---
        if payload["Analog_Temperature"] and payload["Analog_Temperature"] >= TEMP_THRESHOLD_FAN_ON:
            fan_on()
            buzzer.beep(0.1, 2)
        else:
            fan_off()
        if payload["INA219_1_current(mA)"] and payload["INA219_1_current(mA)"] > CURRENT_OVERLOAD_MA:
            relay1.off_all(); relay2.off_all(); fan_on(); buzzer.beep(0.2, 3)

        #--- Publish to AWS IoT Core
        mqtt.publish(PUB_TOPIC, ujson.dumps(payload), qos=1)
        #--- Publish to Blynk
        update_blynk(payload)
        #--- OLED Display (2 main lines: local + ENV)
        if oled:
            oled.fill(0)
            oled.text("T:{0} L:{1}".format(payload["DHT11_Temperature"], payload["Location_Temperature"]), 0, 0)
            oled.text("H:{0} LH:{1}".format(payload["DHT11_Humidity"], payload["Location_Humidity"]), 0, 12)
            oled.show()
        time.sleep(PUBLISH_INTERVAL)
    except Exception as e:
        print("Loop error:", e)
        time.sleep(PUBLISH_INTERVAL)
