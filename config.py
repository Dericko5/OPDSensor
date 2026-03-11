# config.py  –  Centralized configuration for the OBD Dashboard

# ── OBD Connection ─────────────────────────────────────────────────────────────
OBD_DEVICE = "/dev/ttyUSB0"   # USB ELM327 adapter (change to ttyACM0 if needed)

# ELM327 adapters are slow. 2 Hz is realistic for 5 PIDs; raise carefully.
OBD_POLL_HZ    = 2     # How often the background thread queries the adapter
UI_REFRESH_HZ  = 5     # How often the UI reads cached data and redraws
RECONNECT_DELAY_S = 3  # Seconds to wait before retrying a failed connection

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_CSV_PATH = "logs/drive.csv"
LOG_ENABLED  = True

# ── Display ────────────────────────────────────────────────────────────────────
SCREEN_W   = 480
SCREEN_H   = 320
FULLSCREEN = True

# ── Units ──────────────────────────────────────────────────────────────────────
SPEED_UNIT = "mph"   # "mph" or "kph"
TEMP_UNIT  = "C"     # "C"  or "F"

# ── Warning Thresholds ─────────────────────────────────────────────────────────
COOLANT_WARN_C = 95    # Yellow warning above this (°C)
COOLANT_CRIT_C = 105   # Red critical above this  (°C)

RPM_MAX  = 7000        # Your car's approximate redline – scales the RPM bar
RPM_WARN = 5500        # Yellow warning above this
RPM_CRIT = 6500        # Red critical above this

# ── Secondary Panel Rotation ───────────────────────────────────────────────────
# The bottom row of 3 metric panels can cycle through multiple groups.
# Set to 0 to disable rotation and always show the first group.
ROTATION_INTERVAL_S = 8

# ── Blue / Black Color Palette ────────────────────────────────────────────────
C_BG       = "#000a14"   # Near-black with blue tint
C_PANEL    = "#0a1a2e"   # Dark navy
C_BORDER   = "#1a3a5c"   # Navy blue border

C_TEXT_PRI = "#e8f4ff"   # Slightly blue-white
C_TEXT_SEC = "#6a90b8"   # Muted steel blue
C_TEXT_DIM = "#1e3a5a"   # Dark muted blue

C_SPEED    = "#00c8ff"   # Electric cyan-blue
C_RPM      = "#3d8bff"   # Medium blue
C_GOOD     = "#0099ff"   # Blue (connected / OK)
C_WARN     = "#ffcc00"   # Amber (keep — universal warning)
C_CRIT     = "#ff3333"   # Red   (keep — universal critical)
C_NEUTRAL  = "#5588aa"   # Blue-grey neutral

# ── GPIO Physical Buttons (Optional) ──────────────────────────────────────────
#
# The cheapest and most practical way to add user input without a touchscreen
# is to wire momentary push-buttons directly to the Raspberry Pi GPIO pins.
#
# Setup:
#   1. pip install RPi.GPIO
#   2. Wire: button → GPIO pin → GND  (use internal pull-up, no resistor needed)
#   3. Set GPIO_ENABLED = True and configure the pin numbers below.
#   4. Import and call gpio_input.setup(ui) in app.py  (skeleton: gpio_input.py)
#
# Suggested button layout:
#   Function          | GPIO | Physical Header Pin
#   ─────────────────-|──────|────────────────────
#   Cycle metric group| 17   | Pin 11
#   Toggle mph ↔ kph  | 27   | Pin 13
#   Toggle °C  ↔ °F   | 22   | Pin 15
#
# For more input without adding size:
#   • Rotary encoder  – one knob, scroll + click, great UX
#   • USB numpad      – 18 keys, plugs into Pi USB port, small footprint
#   • IR remote       – completely wireless, requires IR receiver module (~$1)
#
GPIO_ENABLED   = False
GPIO_BTN_CYCLE = 17
GPIO_BTN_UNITS = 27
GPIO_BTN_TEMP  = 22
