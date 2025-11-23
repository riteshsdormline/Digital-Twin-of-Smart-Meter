# buzzer.py - simple active buzzer control class
import machine, time

class Buzzer:
    def __init__(self, pin_no, active_high=True):
        self.pin = machine.Pin(pin_no, machine.Pin.OUT)
        self.active_high = active_high
        # set to off initially
        if active_high:
            self.pin.value(0)
        else:
            self.pin.value(1)

    def on(self):
        self.pin.value(1 if self.active_high else 0)

    def off(self):
        self.pin.value(0 if self.active_high else 1)

    def beep(self, duration=0.1, times=1, interval=0.05):
        for _ in range(times):
            self.on()
            time.sleep(duration)
            self.off()
            time.sleep(interval)
