# config.py  –  Centralized configuration for the OBD Dashboard

# ── OBD Connection ─────────────────────────────────────────────────────────────
BLUETOOTH_RFCOMM_DEVICE = "/dev/rfcomm0"

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

# ── Dark Automotive Color Palette ─────────────────────────────────────────────
C_BG       = "#0a0a0a"   # Window / outer background
C_PANEL    = "#141414"   # Card / panel background
C_BORDER   = "#252525"   # Panel border / separator

C_TEXT_PRI = "#f0f0f0"   # Primary text (white)
C_TEXT_SEC = "#888888"   # Secondary / label text (grey)
C_TEXT_DIM = "#444444"   # Dimmed text (dark grey)

C_SPEED    = "#00bfff"   # Speed value (bright blue)
C_RPM      = "#ff6b00"   # RPM value  (orange)
C_GOOD     = "#00cc66"   # OK / connected (green)
C_WARN     = "#ffcc00"   # Warning        (amber)
C_CRIT     = "#ff3333"   # Critical       (red)
C_NEUTRAL  = "#aaaaaa"   # Neutral metric (light grey)

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
