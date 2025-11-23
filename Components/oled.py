from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
i2c = I2C(0, scl=Pin(22), sda=Pin(21))     # Your wiring
oled = SSD1306_I2C(128, 32, i2c)
oled.fill(0)
oled.text("0.91in OLED", 0, 0)
oled.text("128x32 I2C", 0, 12)
oled.show()
