# MicroPython SSD1306 OLED driver, I2C version.
# Works for 0.91", 0.96", or larger SSD1306 I2C displays: 128x32, 128x64, etc.

import time
import framebuf

# Constants for display size
SSD1306_I2C_ADDR = 0x3C

class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.width * self.pages)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.poweron()
        self.init_display()

    def init_display(self):
        for cmd in (
            0xAE,         # Display OFF
            0xD5, 0x80,   # Set display clock divide (0x80 recommended)
            0xA8, self.height - 1, # Set multiplex
            0xD3, 0x00,   # Set display offset to zero
            0x40 | 0x00,  # Set start line at line 0
            0x8D, 0x14 if not self.external_vcc else 0x10,
            0x20, 0x00,   # Set memory mode to horizontal addressing
            0xA1,         # Seg remap
            0xC8,         # COM scan direction
            0xDA, 0x12 if self.height == 64 else 0x02,  # Set COM pins (check datasheet)
            0x81, 0xCF,   # Set contrast
            0xD9, 0xF1 if not self.external_vcc else 0x22,
            0xDB, 0x40,   # Set VCOM detect
            0xA4,         # Resume RAM content display
            0xA6,         # Normal display (not inverted)
            0xAF):        # Display ON
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweron(self):
        pass  # Not required for most I2C setups

    def poweroff(self):
        self.write_cmd(0xAE)

    def contrast(self, contrast):
        self.write_cmd(0x81)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(0xA7 if invert else 0xA6)

    def write_cmd(self, cmd):
        # Should be overridden in I2C/SPI subclass
        raise NotImplementedError

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)

    def show(self):
        # Should be overridden in I2C/SPI subclass
        raise NotImplementedError

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=SSD1306_I2C_ADDR, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, bytearray([0x80, cmd]))

    def show(self):
        for page in range(self.pages):
            self.write_cmd(0xB0 | page)
            self.write_cmd(0x02)   # Set lower column
            self.write_cmd(0x10)   # Set higher column
            start = self.width * page
            end = start + self.width
            control = 0x40
            self.i2c.writeto(self.addr, bytearray([control]) + self.buffer[start:end])

