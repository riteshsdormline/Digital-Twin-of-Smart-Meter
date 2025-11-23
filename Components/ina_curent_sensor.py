"""
Simple INA219 driver for ESP32 (MicroPython)

File: ina219.py

Features:
- Initialize I2C by taking ESP32 SDA and SCL pin numbers from the user
- Read shunt voltage, bus voltage, current, power
- Simple price-calculation helper: price for given duration or energy

Notes:
- Default I2C address is 0x40 (common for INA219 breakout modules)
- Default shunt resistor is 0.1 ohm. If your module uses a different shunt, pass r_shunt to configure().
- The driver writes a calibration value (default 4096). You can change it via configure().

Usage (short):
    from ina219 import INA219
    sensor = INA219(sda_pin=21, scl_pin=22)   # provide ESP32 pin numbers
    sensor.configure(calibration=4096, r_shunt=0.1)
    volts = sensor.get_bus_voltage()
    amps  = sensor.get_current()
    watts = sensor.get_power()
    price = sensor.calculate_price(price_per_kwh=8.0, duration_seconds=3600, avg_power_watts=watts)

"""

from machine import Pin, I2C
import time

# INA219 registers
_REG_CONFIG = 0x00
_REG_SHUNT_VOLTAGE = 0x01
_REG_BUS_VOLTAGE = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIBRATION = 0x05

class INA219:
    def __init__(self, sda_pin: int, scl_pin: int, i2c_freq: int = 400000, address: int = 0x40, r_shunt: float = 0.1):
        """Initialize I2C and basic parameters.

        sda_pin, scl_pin: ESP32 pin numbers for SDA and SCL (integers)
        i2c_freq: I2C frequency in Hz (default 400kHz)
        address: I2C address of INA219 (default 0x40)
        r_shunt: shunt resistor in ohms (default 0.1)
        """
        self.i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=i2c_freq)
        self.address = address
        self.r_shunt = float(r_shunt)

        # Defaults until configure() is called
        self.calibration = None
        self.current_lsb = None
        self.power_lsb = None

        # Try a conservative default calibration so current register returns usable numbers.
        # User should call configure() with values appropriate for their shunt and expected current range.
        try:
            # small delay to let bus settle
            time.sleep_ms(10)
            # optional quick check to see if device responds
            if self.address not in self.i2c.scan():
                # device not found on I2C; still create object but reads will fail until address is correct
                pass
        except Exception:
            pass

    # ---------- low-level helpers ----------
    def _read_register(self, reg):
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        return int.from_bytes(data, 'big')

    def _read_register_signed(self, reg):
        val = self._read_register(reg)
        if val & 0x8000:
            val = val - (1 << 16)
        return val

    def _write_register(self, reg, value):
        data = int(value) & 0xFFFF
        self.i2c.writeto_mem(self.address, reg, data.to_bytes(2, 'big'))

    # ---------- configuration ----------
    def configure(self, calibration: int = 4096, r_shunt: float = None):
        """Write calibration register and compute LSBs.

        calibration: integer to write to calibration register. Typical small boards use values like 4096.
        r_shunt: optional shunt resistor value in ohms; if omitted uses the value passed at init.

        After this call, current and power values will be scaled using computed LSBs.
        """
        if r_shunt is not None:
            self.r_shunt = float(r_shunt)

        self.calibration = int(calibration)
        # write calibration register
        self._write_register(_REG_CALIBRATION, self.calibration)

        # Compute LSBs per datasheet formulas (floating values)
        # current_lsb = 0.04096 / (calibration * R_shunt)
        # power_lsb = 20 * current_lsb
        self.current_lsb = 0.04096 / (self.calibration * self.r_shunt)
        self.power_lsb = 20.0 * self.current_lsb

    # ---------- measurement getters ----------
    def get_shunt_voltage(self) -> float:
        """Return shunt voltage in volts (signed). LSB = 10uV"""
        raw = self._read_register_signed(_REG_SHUNT_VOLTAGE)
        return raw * 10e-6

    def get_bus_voltage(self) -> float:
        """Return bus voltage in volts. Bus register LSB = 4mV, upper 13 bits contain voltage. """
        raw = self._read_register(_REG_BUS_VOLTAGE)
        # drop the lowest 3 status bits
        raw = raw >> 3
        return raw * 4e-3

    def get_current(self) -> float:
        """Return current in amps. Requires configure() to have been called to set calibration.
        If configure() wasn't called, this will attempt to return scaled value but may be incorrect.
        """
        raw = self._read_register_signed(_REG_CURRENT)
        if self.current_lsb is None:
            # fallback: assume a reasonable LSB for small shunts (this is a weak fallback)
            assumed_lsb = 0.0001
            return raw * assumed_lsb
        return raw * self.current_lsb

    def get_power(self) -> float:
        """Return power in watts. power_lsb = 20 * current_lsb (per datasheet)
        Requires configure() to be accurate.
        """
        raw = self._read_register(_REG_POWER)
        if self.power_lsb is None:
            assumed_power_lsb = 0.002  # weak fallback
            return raw * assumed_power_lsb
        return raw * self.power_lsb

    # ---------- utility: energy/cost calculation ----------
    def calculate_price(self, price_per_kwh: float, duration_seconds: int = None, avg_power_watts: float = None) -> float:
        """Calculate price (in same currency as price_per_kwh) for either:
        - a measured instantaneous power held constant for duration_seconds, OR
        - using a provided avg_power_watts over duration_seconds, OR
        - using provided price_per_kwh and avg_power_watts only (duration_seconds required).

        price_per_kwh: cost per kilowatt-hour (e.g., 8.0 for 8 currency units/kWh)
        duration_seconds: how long the power is drawn (seconds)
        avg_power_watts: optional average power in watts; if omitted the current instantaneous power will be used

        Returns: price (float)
        """
        if avg_power_watts is None:
            # use instantaneous measured power
            avg_power_watts = self.get_power()

        if duration_seconds is None:
            raise ValueError('duration_seconds is required to compute energy cost')

        # energy (kWh) = (power_watts * hours) / 1000
        hours = duration_seconds / 3600.0
        energy_kwh = (avg_power_watts * hours) / 1000.0
        return energy_kwh * float(price_per_kwh)

    # convenience: read all at once
    def read_all(self):
        """Return a tuple (shunt_v, bus_v, current_a, power_w)
        Values are floats (volts, volts, amps, watts)
        """
        sv = self.get_shunt_voltage()
        bv = self.get_bus_voltage()
        ca = self.get_current()
        pw = self.get_power()
        return (sv, bv, ca, pw)
