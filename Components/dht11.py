# dht11.py
import dht
from machine import Pin
from time import sleep_ms

class DHT11Sensor:
    def __init__(self, pin):
        self.sensor = dht.DHT11(Pin(pin))
        self.last_temp = None
        self.last_humidity = None

    def read(self):
        """Perform measurement and return {'temperature':x, 'humidity':y} or None on error."""
        try:
            self.sensor.measure()
            self.last_temp = self.sensor.temperature()
            self.last_humidity = self.sensor.humidity()
            return {'temperature': self.last_temp, 'humidity': self.last_humidity}
        except Exception as e:
            print("DHT11 read error:", e)
            return None

    def get_temperature(self):
        return self.last_temp

    def get_humidity(self):
        return self.last_humidity
