# blynk_manager.py
import time
import urequests
import network

class BlynkManager:
    """
    Simple MicroPython Blynk helper using Blynk Cloud HTTP API.
    """

    def __init__(self, auth_token, ssid=None, password=None):
        self.auth_token = auth_token
        self.ssid = ssid
        self.password = password
        # prefer the modern blynk.cloud endpoint
        self.base_url = "https://blynk.cloud/external/api/update?token=" + self.auth_token
        self.wlan = network.WLAN(network.STA_IF)

    def ensure_wifi(self):
        if self.ssid and self.password:
            if not self.wlan.isconnected():
                print("Connecting to WiFi for Blynk...")
                self.wlan.active(True)
                self.wlan.connect(self.ssid, self.password)
                timeout = 10
                while not self.wlan.isconnected() and timeout > 0:
                    time.sleep(1)
                    timeout -= 1
            return self.wlan.isconnected()
        return True  # assume host device has wifi (for PC testing)

    def send(self, pin, value):
        """Send single value to virtual pin V{pin}"""
        try:
            if not self.ensure_wifi():
                print("Blynk: WiFi not available")
                return False
            url = "{}&V{}={}".format(self.base_url, pin, value)
            r = urequests.get(url, timeout=5)
            r.close()
            return True
        except Exception as e:
            print("Blynk send error:", e)
            return False

    # convenience wrappers
    def send_dht(self, dht_sensor, v_temp, v_hum):
        data = dht_sensor.read()
        if data:
            self.send(v_temp, data['temperature'])
            self.send(v_hum, data['humidity'])
            return True
        return False
