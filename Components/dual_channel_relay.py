
from machine import Pin

class DualRelay:

    def __init__(self, ch1_pin, ch2_pin, active_high=True):
        self.relay1 = Pin(ch1_pin, Pin.OUT)
        self.relay2 = Pin(ch2_pin, Pin.OUT)
        self.active_high = active_high
        
        # Start with both relays off
        self.off(1)
        self.off(2)
    
    def on(self, channel):
        """Turn ON specified relay channel (1 or 2)."""
        if channel == 1:
            self.relay1.value(1 if self.active_high else 0)
        elif channel == 2:
            self.relay2.value(1 if self.active_high else 0)
    
    def off(self, channel):
        """Turn OFF specified relay channel (1 or 2)."""
        if channel == 1:
            self.relay1.value(0 if self.active_high else 1)
        elif channel == 2:
            self.relay2.value(0 if self.active_high else 1)
    
    def toggle(self, channel):
        """Toggle specified relay channel state."""
        if channel == 1:
            self.relay1.value(not self.relay1.value())
        elif channel == 2:
            self.relay2.value(not self.relay2.value())
    
    def state(self, channel):
        """
        Get current state of relay channel.
        
        Returns:
            str: "ON" or "OFF"
        """
        if channel == 1:
            relay_state = self.relay1.value()
        elif channel == 2:
            relay_state = self.relay2.value()
        else:
            return "UNKNOWN"
        
        if (self.active_high and relay_state == 1) or (not self.active_high and relay_state == 0):
            return "ON"
        else:
            return "OFF"
    
    def control_current(self, channel, enable):
        """
        Control current flow through relay channel.
        
        Args:
            channel (int): Relay channel (1 or 2)
            enable (bool): True to allow current flow, False to stop
        """
        if enable:
            self.on(channel)
        else:
            self.off(channel)
        print(f"Channel {channel} current flow: {'ENABLED' if enable else 'BLOCKED'}")
    
    def all_on(self):
        """Turn both relays ON."""
        self.on(1)
        self.on(2)
    
    def all_off(self):
        """Turn both relays OFF."""
        self.off(1)
        self.off(2)