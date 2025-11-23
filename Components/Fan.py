# dcfan.py
# A MicroPython class for controlling a 5V DC fan via a relay with an ESP32.

from machine import Pin

class DCFan:

    def __init__(self, pin, active_high=True):
        self._relay = Pin(pin, Pin.OUT)
        self._active_high = active_high
        # Start with the fan turned off
        self.off()
    
    def on(self):
        self._relay.value(1 if self._active_high else 0)
    
    def off(self):
        self._relay.value(0 if self._active_high else 1)
    
    def state(self):

        relay_state = self._relay.value()
        if (self._active_high and relay_state == 1) or (not self._active_high and relay_state == 0):
            return "ON"
        else:
            return "OFF"