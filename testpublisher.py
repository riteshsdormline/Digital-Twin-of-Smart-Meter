import time
from machine import Pin, I2C

# Import your drivers
from Components.ina_curent_sensor import INA219
from Components.buzzer import Buzzer
from Components.ssd1306 import SSD1306_I2C

# Pin definitions (adjust as needed)
INA_SDA = 21
INA_SCL = 22
BUZZER_PIN = 13
OLED_SDA = 21
OLED_SCL = 22

# Initialize I2C bus (common for both INA219 and OLED)
i2c = I2C(0, scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=400000)

# Initialize components
ina = INA219(sda_pin=INA_SDA, scl_pin=INA_SCL)
ina.configure()
buzzer = Buzzer(BUZZER_PIN, active_high=True)
oled = SSD1306_I2C(128, 32, i2c)  # Change to 128,64 if using 64px OLED

while True:
    try:
        # Read INA219 values
        shunt_v, bus_v, current_a, power_w = ina.read_all()
        current_mA = round(current_a * 1000, 2)
        power_mW = round(power_w * 1000, 2)

        # Prepare display text
        oled.fill(0)
        oled.text("INA219 Test", 0, 0)
        oled.text("V: {:.2f}V".format(bus_v), 0, 10)
        oled.text("I: {:.0f}mA".format(current_mA), 0, 20)
        oled.text("P: {:.0f}mW".format(power_mW), 64, 20)
        oled.show()

        print("INA219: V={:.2f}V  I={:.0f}mA  P={:.0f}mW".format(bus_v, current_mA, power_mW))
        buzzer.beep(duration=0.1, times=1)  # success beep
    except Exception as e:
        # Error feedback
        oled.fill(0)
        oled.text("INA219 ERROR", 0, 0)
        oled.show()
        print("INA219 ERROR:", e)
        buzzer.beep(duration=0.1, times=3)  # multiple beeps on error
    time.sleep(2)
