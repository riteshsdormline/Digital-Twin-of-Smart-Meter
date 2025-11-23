# analog_temp.py
# MicroPython class for analog temperature sensors (LM35, TMP36, NTC thermistor, etc.)

from machine import ADC, Pin
from time import sleep_ms

class AnalogTempSensor:
    
    def __init__(self, pin, sensor_type='lm35', vref=3.3, adc_bits=12):
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_11DB)  # Full range 0-3.3V
        self.adc.width(ADC.WIDTH_12BIT)  # 12-bit resolution
        self.sensor_type = sensor_type
        self.vref = vref
        self.max_adc = (2 ** adc_bits) - 1  # 4095 for 12-bit
        self.last_temp = None
        
    def read_voltage(self):

        raw_value = self.adc.read()
        voltage = (raw_value / self.max_adc) * self.vref
        return voltage
    
    def read_temperature(self):

        voltage = self.read_voltage()
        
        if self.sensor_type == 'lm35':
            # LM35: 10mV per °C, 0V = 0°C
            temperature = voltage * 100
            
        elif self.sensor_type == 'tmp36':
            # TMP36: 10mV per °C, 500mV = 0°C
            temperature = (voltage - 0.5) * 100
            
        elif self.sensor_type == 'custom':
            # For custom sensors or NTC thermistors
            # You'll need to implement your specific conversion
            # This is a placeholder - implement your own conversion
            temperature = voltage * 100  # Example conversion
            
        else:
            raise ValueError("Unsupported sensor type. Use 'lm35', 'tmp36', or 'custom'")
        
        self.last_temp = temperature
        return temperature
    
    def read_temperature_fahrenheit(self):
        """
        Read temperature in Fahrenheit.
        
        Returns:
            float: Temperature in Fahrenheit
        """
        temp_c = self.read_temperature()
        if temp_c is not None:
            return (temp_c * 9/5) + 32
        return None
    
    def get_last_temperature(self):
        """Get last temperature reading."""
        return self.last_temp
    
    def read_average(self, samples=10, delay_ms=100):

        total = 0
        for i in range(samples):
            total += self.read_temperature()
            if i < samples - 1:  # No delay after last sample
                sleep_ms(delay_ms)
        
        average_temp = total / samples
        self.last_temp = average_temp
        return average_temp