"""
arduino_link.py
================
Handles the USB serial connection to an Arduino. Auto-detects the port,
sends one character per confirmed gesture, and reconnects automatically
if the Arduino gets unplugged mid-session.

SETUP: pip install pyserial

Usage from another script:
    from arduino_link import ArduinoLink

    link = ArduinoLink()
    link.connect()          # safe to call even if not plugged in yet
    ...
    link.send_gesture("FIST")   # sends '0\\n' if connected, no-op + retry otherwise
"""

import time

import serial
from serial.tools import list_ports

BAUD_RATE = 9600

# One character per gesture, must match the switch/case in the Arduino sketch.
GESTURE_COMMANDS = {
    "FIST": "0",
    "OPEN_HAND": "1",
    "POINT": "2",
    "THUMBS_UP": "3",
    "PEACE": "4",
    "OK": "5",
    "ROCK_N_ROLL": "6",
    "THREE": "7",
    "FOUR": "8",
}

# If auto-detect picks the wrong port (or you have multiple Arduino-like
# devices plugged in), set this to the exact port name and auto-detect
# will be skipped, e.g. PORT_OVERRIDE = "COM5"
PORT_OVERRIDE = None

# How often to retry connecting while the Arduino isn't found (seconds)
RECONNECT_INTERVAL_SEC = 3

# Common identifying text in Arduino USB-serial descriptions across
# different boards/clones (Uno, Nano w/ CH340, etc.)
ARDUINO_HINTS = ["arduino", "ch340", "usb-serial", "usb serial"]


def find_arduino_port():
    """Returns the first COM port that looks like an Arduino, or None."""
    for port in list_ports.comports():
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if any(hint in description or hint in manufacturer for hint in ARDUINO_HINTS):
            return port.device
    return None


class ArduinoLink:
    def __init__(self, baud_rate=BAUD_RATE):
        self.baud_rate = baud_rate
        self.serial_conn = None
        self.port_name = None
        self._last_connect_attempt = 0

    def connect(self):
        """Tries to open the serial connection. Safe to call repeatedly - it
        no-ops if already connected, and won't spam retries faster than
        RECONNECT_INTERVAL_SEC."""
        if self.is_connected():
            return True

        now = time.time()
        if now - self._last_connect_attempt < RECONNECT_INTERVAL_SEC:
            return False
        self._last_connect_attempt = now

        port = PORT_OVERRIDE or find_arduino_port()
        if port is None:
            return False

        try:
            self.serial_conn = serial.Serial(port, self.baud_rate, timeout=1)
            time.sleep(2)  # Arduino resets on serial connect; give it time to boot
            self.port_name = port
            print(f"[Arduino] Connected on {port}")
            return True
        except serial.SerialException as e:
            print(f"[Arduino] Could not open {port}: {e}")
            self.serial_conn = None
            return False

    def is_connected(self):
        return self.serial_conn is not None and self.serial_conn.is_open

    def send_gesture(self, gesture_name):
        """Sends the command byte for a gesture. Returns True if sent."""
        if not self.is_connected():
            self.connect()  # try to (re)connect; will just fail quietly if still not plugged in
            if not self.is_connected():
                return False

        command = GESTURE_COMMANDS.get(gesture_name)
        if command is None:
            return False  # no mapping for this gesture (e.g. TWO_FINGERS/UNKNOWN) - nothing to send

        try:
            self.serial_conn.write((command + "\n").encode("utf-8"))
            return True
        except serial.SerialException as e:
            print(f"[Arduino] Send failed, marking disconnected: {e}")
            self.close()
            return False

    def close(self):
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except serial.SerialException:
                pass
        self.serial_conn = None