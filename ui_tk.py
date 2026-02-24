# ui_tk.py  –  Dashboard UI  (480 × 320, 3.5" SPI touchscreen)
#
# Three display states:
#   DISCONNECTED  – OBD adapter not found; pulsing red alert + retry dots
#   WAITING       – Adapter connected but engine is off / no PID data yet
#   LIVE          – Full telemetry dashboard with rotating secondary panels
#
# Touch gestures (LIVE screen):
#   Tap bottom row  → cycle to next secondary metric group
#   Tap speed panel → toggle mph ↔ kph
#
# Layout (LIVE state, 480 × 320):
#   ┌───────────────────────────────────────┐ ← 30 px status bar
#   │ ● CONNECTED                 12:34:56 │
#   ├──────────────────┬────────────────────┤
#   │       67         │      3,450         │ ← ~58% height
#   │       mph        │      RPM  ████░░   │
#   ├────────┬──────────┴──────────┬────────┤
#   │  92°C  │       45%           │  62%   │ ← ~42% height
#   │COOLANT │     THROTTLE        │  LOAD  │
#   └────────┴─────────────────────┴────────┘

import tkinter as tk
from datetime import datetime

import config
from config import (
    BLUETOOTH_RFCOMM_DEVICE,
    C_BG, C_PANEL, C_BORDER,
    C_TEXT_PRI, C_TEXT_SEC, C_TEXT_DIM,
    C_SPEED, C_RPM, C_GOOD, C_WARN, C_CRIT, C_NEUTRAL,
    COOLANT_WARN_C, COOLANT_CRIT_C,
    RPM_MAX, RPM_WARN, RPM_CRIT,
    ROTATION_INTERVAL_S, FULLSCREEN,
)

_FF = "DejaVu Sans"   # Guaranteed available on Raspberry Pi OS


# ── Metric colour helpers ──────────────────────────────────────────────────────

def _rpm_color(val: float) -> str:
    if val >= RPM_CRIT:
        return C_CRIT
    if val >= RPM_WARN:
        return C_WARN
    return C_RPM


def _coolant_color(val_c: float) -> str:
    if val_c >= COOLANT_CRIT_C:
        return C_CRIT
    if val_c >= COOLANT_WARN_C:
        return C_WARN
    return C_GOOD


# ── Metric formatters  (raw: pint Quantity) → (display_str, 0-1 pct, color) ──

def _fmt_coolant(raw):
    c = raw.to("degC").magnitude
    disp = (
        f"{raw.to('degF').magnitude:.0f}°F"
        if config.TEMP_UNIT == "F"
        else f"{c:.0f}°C"
    )
    return disp, min(c / 120.0, 1.0), _coolant_color(c)


def _fmt_throttle(raw):
    v = raw.magnitude
    return f"{v:.0f}%", v / 100.0, C_NEUTRAL


def _fmt_load(raw):
    v = raw.magnitude
    color = C_GOOD if v < 50 else (C_WARN if v < 80 else C_CRIT)
    return f"{v:.0f}%", v / 100.0, color


# ── Secondary panel groups ─────────────────────────────────────────────────────
# Each group is a list of 3 tuples: (data_key, display_label, formatter_fn).
# Tap the bottom row to cycle groups. Add more groups as new PIDs are supported.

SECONDARY_GROUPS = [
    [
        ("coolant_temp", "COOLANT",  _fmt_coolant),
        ("throttle_pos", "THROTTLE", _fmt_throttle),
        ("engine_load",  "ENG LOAD", _fmt_load),
    ],
    # Example second group – uncomment + add PIDs to obd_service.py to activate:
    # [
    #     ("intake_temp", "INTAKE",  _fmt_intake),
    #     ("engine_load", "LOAD",    _fmt_load),
    #     ("coolant_temp","COOLANT", _fmt_coolant),
    # ],
]


# ── Canvas progress bar helper ─────────────────────────────────────────────────

def _draw_bar(canvas: tk.Canvas, pct: float, color: str) -> None:
    canvas.update_idletasks()
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 4:
        return
    canvas.delete("all")
    canvas.create_rectangle(0, 0, w, h, fill="#1c1c1c", outline="")
    fill_w = max(0, min(int(w * pct), w))
    if fill_w > 0:
        canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")


# ── Widget helpers ─────────────────────────────────────────────────────────────

def _panel(parent: tk.Widget) -> tk.Frame:
    return tk.Frame(
        parent, bg=C_PANEL,
        highlightbackground=C_BORDER, highlightthickness=1,
    )


def _status_bar(parent: tk.Widget, dot_color: str, label_text: str) -> tuple:
    """30 px status bar. Returns (frame, clock_label)."""
    bar = tk.Frame(parent, bg="#0d0d0d", height=30)
    bar.pack(fill="x")
    bar.pack_propagate(False)

    tk.Label(bar, text="●", font=(_FF, 10), bg="#0d0d0d", fg=dot_color).pack(
        side="left", padx=(10, 2)
    )
    tk.Label(bar, text=label_text, font=(_FF, 9), bg="#0d0d0d", fg=dot_color).pack(
        side="left"
    )
    clock_lbl = tk.Label(bar, text="", font=(_FF, 9), bg="#0d0d0d", fg=C_TEXT_SEC)
    clock_lbl.pack(side="right", padx=10)
    return bar, clock_lbl


# ── Main UI class ──────────────────────────────────────────────────────────────

class DashboardUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OBD Dashboard")
        self.root.configure(bg=C_BG)
        self.root.attributes("-fullscreen", FULLSCREEN)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self._screen: str | None = None
        self._anim_after     = None
        self._rotation_after = None
        self._rotation_idx   = 0
        self._live_data: dict = {}

        self._build_disconnected()
        self._build_waiting()
        self._build_live()

        self._tick_clock()

    # ── Screen builders ────────────────────────────────────────────────────────

    def _build_disconnected(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._disc_frame = f

        center = tk.Frame(f, bg=C_BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        cv = tk.Canvas(center, width=70, height=70, bg=C_BG, highlightthickness=0)
        cv.pack(pady=(0, 12))
        cv.create_oval(7, 7, 63, 63, outline="#2a0000", width=2)
        self._disc_ring = cv.create_oval(7, 7, 63, 63, outline=C_CRIT, width=4)
        self._disc_x    = cv.create_text(35, 35, text="✕", font=(_FF, 20, "bold"), fill=C_CRIT)
        self._disc_cv   = cv

        tk.Label(center, text="NO OBD CONNECTION",
                 font=(_FF, 16, "bold"), bg=C_BG, fg=C_CRIT).pack()
        tk.Label(center, text="Bluetooth adapter not found",
                 font=(_FF, 10), bg=C_BG, fg=C_TEXT_SEC).pack(pady=(6, 2))
        tk.Label(center, text=BLUETOOTH_RFCOMM_DEVICE,
                 font=(_FF, 9), bg=C_BG, fg=C_TEXT_DIM).pack()

        self._disc_retry = tk.Label(center, text="Retrying  ○○○",
                                     font=(_FF, 10), bg=C_BG, fg=C_TEXT_SEC)
        self._disc_retry.pack(pady=(12, 0))

    def _build_waiting(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._wait_frame = f

        _, self._wait_clock = _status_bar(f, C_GOOD, "OBD CONNECTED")

        center = tk.Frame(f, bg=C_BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        cv = tk.Canvas(center, width=56, height=56, bg=C_BG, highlightthickness=0)
        cv.pack(pady=(0, 12))
        self._wait_ring = cv.create_oval(4, 4, 52, 52, outline=C_GOOD, width=3)
        self._wait_dot  = cv.create_oval(16, 16, 40, 40, fill=C_GOOD, outline="")
        self._wait_cv   = cv

        tk.Label(center, text="ENGINE OFF  /  STANDBY",
                 font=(_FF, 14, "bold"), bg=C_BG, fg=C_TEXT_PRI).pack()
        tk.Label(center, text="Waiting for engine data",
                 font=(_FF, 10), bg=C_BG, fg=C_TEXT_SEC).pack(pady=(8, 3))
        tk.Label(center, text="Start the vehicle to begin monitoring",
                 font=(_FF, 9), bg=C_BG, fg=C_TEXT_DIM).pack()

    def _build_live(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._live_frame = f

        _, self._live_clock = _status_bar(f, C_GOOD, "CONNECTED")

        main = tk.Frame(f, bg=C_BG)
        main.pack(fill="both", expand=True)
        main.rowconfigure(0, weight=58)
        main.rowconfigure(1, weight=42)
        main.columnconfigure(0, weight=1)

        # ── Top row: Speed + RPM ──────────────────────────────────────────────
        top = tk.Frame(main, bg=C_BG)
        top.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 2))
        top.columnconfigure(0, weight=55)
        top.columnconfigure(1, weight=45)
        top.rowconfigure(0, weight=1)

        # Speed panel – tap to toggle mph/kph
        spd = _panel(top)
        spd.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        spd.columnconfigure(0, weight=1)
        spd.rowconfigure(1, weight=1)
        spd.bind("<Button-1>", self._toggle_speed_unit)

        tk.Label(spd, text="SPEED", font=(_FF, 8), bg=C_PANEL, fg=C_TEXT_SEC).grid(
            row=0, column=0, sticky="nw", padx=8, pady=(6, 0),
        )
        self._speed_var = tk.StringVar(value="--")
        spd_val = tk.Label(spd, textvariable=self._speed_var,
                           font=(_FF, 54, "bold"), bg=C_PANEL, fg=C_SPEED)
        spd_val.grid(row=1, column=0, sticky="nsew")
        spd_val.bind("<Button-1>", self._toggle_speed_unit)

        self._speed_unit_lbl = tk.Label(spd, text=config.SPEED_UNIT.upper(),
                                         font=(_FF, 11), bg=C_PANEL, fg=C_TEXT_SEC)
        self._speed_unit_lbl.grid(row=2, column=0, sticky="s", pady=(0, 6))
        self._speed_unit_lbl.bind("<Button-1>", self._toggle_speed_unit)

        # RPM panel
        rpm = _panel(top)
        rpm.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        rpm.columnconfigure(0, weight=1)
        rpm.rowconfigure(1, weight=1)

        tk.Label(rpm, text="RPM", font=(_FF, 8), bg=C_PANEL, fg=C_TEXT_SEC).grid(
            row=0, column=0, sticky="nw", padx=8, pady=(6, 0),
        )
        self._rpm_var = tk.StringVar(value="----")
        self._rpm_lbl = tk.Label(rpm, textvariable=self._rpm_var,
                                  font=(_FF, 36, "bold"), bg=C_PANEL, fg=C_RPM)
        self._rpm_lbl.grid(row=1, column=0, sticky="nsew")

        self._rpm_bar = tk.Canvas(rpm, height=7, bg="#1c1c1c", highlightthickness=0)
        self._rpm_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))

        # ── Bottom row: rotating metric panels ────────────────────────────────
        bot = tk.Frame(main, bg=C_BG)
        bot.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        bot.rowconfigure(0, weight=1)
        for col in range(3):
            bot.columnconfigure(col, weight=1)

        # Tap anywhere on the bottom row to cycle metric groups
        bot.bind("<Button-1>", self._on_bottom_tap)

        self._metric_widgets: list[tuple] = []
        padx_map = [(0, 2), (2, 2), (2, 0)]

        for i in range(3):
            p = _panel(bot)
            p.grid(row=0, column=i, sticky="nsew", padx=padx_map[i])
            p.columnconfigure(0, weight=1)
            p.rowconfigure(1, weight=1)
            p.bind("<Button-1>", self._on_bottom_tap)

            title_lbl = tk.Label(p, text="---", font=(_FF, 8),
                                  bg=C_PANEL, fg=C_TEXT_SEC)
            title_lbl.grid(row=0, column=0, sticky="nw", padx=7, pady=(5, 0))
            title_lbl.bind("<Button-1>", self._on_bottom_tap)

            val_lbl = tk.Label(p, text="--", font=(_FF, 20, "bold"),
                                bg=C_PANEL, fg=C_TEXT_PRI)
            val_lbl.grid(row=1, column=0, sticky="nsew")
            val_lbl.bind("<Button-1>", self._on_bottom_tap)

            bar = tk.Canvas(p, height=5, bg="#1c1c1c", highlightthickness=0)
            bar.grid(row=2, column=0, sticky="ew", padx=7, pady=(0, 6))

            self._metric_widgets.append((title_lbl, val_lbl, bar))

    # ── Public state API ───────────────────────────────────────────────────────

    def show_disconnected(self) -> None:
        if self._screen == "disconnected":
            return
        self._hide_all()
        self._disc_frame.pack(fill="both", expand=True)
        self._screen = "disconnected"
        self._anim_disc_phase = 0
        self._anim_disc_dots  = 0
        self._animate_disc()

    def show_waiting(self) -> None:
        if self._screen == "waiting":
            return
        self._hide_all()
        self._wait_frame.pack(fill="both", expand=True)
        self._screen = "waiting"
        self._anim_wait_phase = 0
        self._animate_wait()

    def show_live(self, data: dict) -> None:
        if self._screen != "live":
            self._hide_all()
            self._live_frame.pack(fill="both", expand=True)
            self._screen = "live"
            self._start_rotation()
        self._live_data = data
        self._refresh_live(data)

    # ── Touch handlers ─────────────────────────────────────────────────────────

    def _toggle_speed_unit(self, _event=None) -> None:
        """Tap the speed panel to flip between mph and kph."""
        config.SPEED_UNIT = "kph" if config.SPEED_UNIT == "mph" else "mph"
        self._speed_unit_lbl.config(text=config.SPEED_UNIT.upper())
        self._refresh_live(self._live_data)

    def _on_bottom_tap(self, _event=None) -> None:
        """Tap the bottom metric row to cycle to the next group."""
        if self._screen != "live":
            return
        self._rotation_idx = (self._rotation_idx + 1) % len(SECONDARY_GROUPS)
        self._refresh_live(self._live_data)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _hide_all(self) -> None:
        for frame in (self._disc_frame, self._wait_frame, self._live_frame):
            frame.pack_forget()
        if self._anim_after:
            self.root.after_cancel(self._anim_after)
            self._anim_after = None
        if self._rotation_after:
            self.root.after_cancel(self._rotation_after)
            self._rotation_after = None

    # ── Animations ─────────────────────────────────────────────────────────────

    def _animate_disc(self) -> None:
        if self._screen != "disconnected":
            return
        self._anim_disc_phase = (self._anim_disc_phase + 1) % 16
        bright = self._anim_disc_phase < 8
        ring_c = C_CRIT if bright else "#3a0000"
        self._disc_cv.itemconfig(self._disc_ring, outline=ring_c)
        self._disc_cv.itemconfig(self._disc_x, fill=ring_c)
        self._anim_disc_dots = (self._anim_disc_dots + 1) % 4
        d = self._anim_disc_dots
        self._disc_retry.config(text=f"Retrying  {'●' * d}{'○' * (3 - d)}")
        self._anim_after = self.root.after(350, self._animate_disc)

    def _animate_wait(self) -> None:
        if self._screen != "waiting":
            return
        self._anim_wait_phase = (self._anim_wait_phase + 1) % 40
        t = abs(self._anim_wait_phase - 20) / 20.0
        g = int(0x33 + (0xcc - 0x33) * (1.0 - t))
        color = f"#00{g:02x}44"
        self._wait_cv.itemconfig(self._wait_ring, outline=color)
        self._wait_cv.itemconfig(self._wait_dot,  fill=color)
        self._anim_after = self.root.after(50, self._animate_wait)

    # ── Panel rotation ─────────────────────────────────────────────────────────

    def _start_rotation(self) -> None:
        if ROTATION_INTERVAL_S > 0 and len(SECONDARY_GROUPS) > 1:
            self._rotation_after = self.root.after(
                int(ROTATION_INTERVAL_S * 1000), self._rotate
            )

    def _rotate(self) -> None:
        if self._screen != "live":
            return
        self._rotation_idx = (self._rotation_idx + 1) % len(SECONDARY_GROUPS)
        self._refresh_live(self._live_data)
        self._start_rotation()

    # ── Live data refresh ──────────────────────────────────────────────────────

    def _refresh_live(self, data: dict) -> None:
        speed = data.get("speed")
        if speed:
            mag = (
                speed.to("mph").magnitude
                if config.SPEED_UNIT == "mph"
                else speed.to("kph").magnitude
            )
            self._speed_var.set(f"{mag:.0f}")
        else:
            self._speed_var.set("--")

        rpm = data.get("rpm")
        if rpm:
            val = rpm.magnitude
            self._rpm_var.set(f"{val:,.0f}")
            color = _rpm_color(val)
            self._rpm_lbl.config(fg=color)
            _draw_bar(self._rpm_bar, val / RPM_MAX, color)
        else:
            self._rpm_var.set("----")
            self._rpm_lbl.config(fg=C_RPM)
            _draw_bar(self._rpm_bar, 0, C_RPM)

        group = SECONDARY_GROUPS[self._rotation_idx % len(SECONDARY_GROUPS)]
        for i, (key, label, fmt) in enumerate(group):
            title_lbl, val_lbl, bar = self._metric_widgets[i]
            title_lbl.config(text=label)
            raw = data.get(key)
            if raw is None:
                val_lbl.config(text="--", fg=C_NEUTRAL)
                _draw_bar(bar, 0, C_NEUTRAL)
            else:
                disp, pct, color = fmt(raw)
                val_lbl.config(text=disp, fg=color)
                _draw_bar(bar, pct, color)

    # ── Clock ──────────────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self._wait_clock.config(text=now)
        self._live_clock.config(text=now)
        self.root.after(1000, self._tick_clock)
