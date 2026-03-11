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
    OBD_DEVICE,
    C_BG, C_PANEL, C_BORDER,
    C_TEXT_PRI, C_TEXT_SEC, C_TEXT_DIM,
    C_SPEED, C_RPM, C_GOOD, C_WARN, C_CRIT, C_NEUTRAL,
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


# ── Metric formatters  (raw: pint Quantity) → (display_str, 0-1 pct, color) ──

def _fmt_throttle(raw):
    v = raw.magnitude
    return f"{v:.0f}%", v / 100.0, C_NEUTRAL


def _fmt_load(raw):
    v = raw.magnitude
    color = C_GOOD if v < 50 else (C_WARN if v < 80 else C_CRIT)
    return f"{v:.0f}%", v / 100.0, color


def _fmt_intake(raw):
    c = raw.to("degC").magnitude
    disp = (
        f"{raw.to('degF').magnitude:.0f}°F"
        if config.TEMP_UNIT == "F"
        else f"{c:.0f}°C"
    )
    return disp, min(max(c + 20, 0) / 80.0, 1.0), C_NEUTRAL


def _fmt_fuel(raw):
    v = raw.magnitude
    color = C_CRIT if v < 10 else (C_WARN if v < 20 else C_GOOD)
    return f"{v:.0f}%", v / 100.0, color


def _fmt_timing(raw):
    v = raw.magnitude   # degrees advance
    color = C_WARN if v < 0 else C_GOOD
    return f"{v:.0f}°", min(max(v / 45.0, 0.0), 1.0), color


def _fmt_fuel_trim(raw):
    v = raw.magnitude   # percent; healthy = near 0
    color = C_GOOD if abs(v) < 10 else (C_WARN if abs(v) < 20 else C_CRIT)
    return f"{v:+.1f}%", min(max((v + 25) / 50.0, 0.0), 1.0), color


def _fmt_maf(raw):
    v = raw.magnitude   # g/s
    return f"{v:.1f} g/s", min(v / 80.0, 1.0), C_NEUTRAL


def _fmt_run_time(raw):
    secs = int(raw.to("second").magnitude)
    mins, s = divmod(secs, 60)
    return f"{mins:02d}:{s:02d}", min(secs / 3600.0, 1.0), C_NEUTRAL


# ── Secondary panel groups ─────────────────────────────────────────────────────
# Each group is a list of 3 tuples: (data_key, display_label, formatter_fn).
# Tap the bottom row to cycle through groups.

SECONDARY_GROUPS = [
    [   # Page 1 – core vitals
        ("fuel_level",   "FUEL",     _fmt_fuel),
        ("throttle_pos", "THROTTLE", _fmt_throttle),
        ("engine_load",  "ENG LOAD", _fmt_load),
    ],
    [   # Page 2 – air & ignition
        ("intake_temp",  "INTAKE T", _fmt_intake),
        ("timing_adv",   "TIMING",   _fmt_timing),
        ("short_fuel_t", "S TRIM",   _fmt_fuel_trim),
    ],
    [   # Page 3 – flow & history
        ("maf",          "AIR FLOW", _fmt_maf),
        ("long_fuel_t",  "L TRIM",   _fmt_fuel_trim),
        ("run_time",     "RUN TIME", _fmt_run_time),
    ],
]

# ── Graph metric definitions ────────────────────────────────────────────────────
# (data_key, label, unit, y_min, y_max, color, value_extractor)
GRAPH_METRICS = [
    ("rpm",          "RPM",      "rpm", 0,  8000, C_RPM,     lambda r: r.magnitude),
    ("speed",        "SPEED",    "mph", 0,  160,  C_SPEED,   lambda r: r.to("mph").magnitude),
    ("engine_load",  "ENG LOAD", "%",   0,  100,  C_NEUTRAL, lambda r: r.magnitude),
    ("throttle_pos", "THROTTLE", "%",   0,  100,  C_NEUTRAL, lambda r: r.magnitude),
    ("fuel_level",   "FUEL",     "%",   0,  100,  C_GOOD,    lambda r: r.magnitude),
]


# ── Canvas progress bar helper ─────────────────────────────────────────────────

def _draw_bar(canvas: tk.Canvas, pct: float, color: str) -> None:
    canvas.update_idletasks()
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 4:
        return
    canvas.delete("all")
    canvas.create_rectangle(0, 0, w, h, fill="#0a1a2e", outline="")
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
    bar = tk.Frame(parent, bg="#000a14", height=30)
    bar.pack(fill="x")
    bar.pack_propagate(False)

    tk.Label(bar, text="●", font=(_FF, 10), bg="#000a14", fg=dot_color).pack(
        side="left", padx=(10, 2)
    )
    tk.Label(bar, text=label_text, font=(_FF, 9), bg="#000a14", fg=dot_color).pack(
        side="left"
    )
    clock_lbl = tk.Label(bar, text="", font=(_FF, 9), bg="#000a14", fg=C_TEXT_SEC)
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
        self._last_dtcs_rendered: list = []
        self.dismiss_codes = None   # set by AppController after construction

        self._graph_mode: bool = False
        self._graph_metric_idx: int = 0
        self._last_history: list = []

        self._build_disconnected()
        self._build_waiting()
        self._build_live()
        self._build_codes()
        self._build_graph()

        self._tick_clock()

    # ── Screen builders ────────────────────────────────────────────────────────

    def _build_disconnected(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._disc_frame = f

        center = tk.Frame(f, bg=C_BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        cv = tk.Canvas(center, width=70, height=70, bg=C_BG, highlightthickness=0)
        cv.pack(pady=(0, 12))
        cv.create_oval(7, 7, 63, 63, outline="#001a3a", width=2)
        self._disc_ring = cv.create_oval(7, 7, 63, 63, outline=C_CRIT, width=4)
        self._disc_x    = cv.create_text(35, 35, text="✕", font=(_FF, 20, "bold"), fill=C_CRIT)
        self._disc_cv   = cv

        tk.Label(center, text="NO OBD CONNECTION",
                 font=(_FF, 16, "bold"), bg=C_BG, fg=C_CRIT).pack()
        tk.Label(center, text="USB OBD adapter not found",
                 font=(_FF, 10), bg=C_BG, fg=C_TEXT_SEC).pack(pady=(6, 2))
        tk.Label(center, text=OBD_DEVICE,
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

        bar = tk.Frame(f, bg="#000a14", height=30)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="●", font=(_FF, 10), bg="#000a14", fg=C_GOOD).pack(
            side="left", padx=(10, 2)
        )
        tk.Label(bar, text="CONNECTED", font=(_FF, 9), bg="#000a14", fg=C_GOOD).pack(
            side="left"
        )
        self._live_codes_lbl = tk.Label(bar, text="", font=(_FF, 8),
                                         bg="#000a14", fg=C_GOOD)
        self._live_codes_lbl.pack(side="left", padx=(10, 0))

        graph_btn = tk.Label(bar, text="  GRAPH  ", font=(_FF, 8, "bold"),
                             bg=C_BORDER, fg=C_TEXT_PRI)
        graph_btn.pack(side="right", padx=(0, 4), fill="y")
        graph_btn.bind("<Button-1>", self._on_graph_btn)

        self._live_clock = tk.Label(bar, text="", font=(_FF, 9),
                                     bg="#000a14", fg=C_TEXT_SEC)
        self._live_clock.pack(side="right", padx=10)

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

        self._rpm_bar = tk.Canvas(rpm, height=7, bg="#0a1a2e", highlightthickness=0)
        self._rpm_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 8))

        # ── Bottom row: rotating metric panels ────────────────────────────────
        bot = tk.Frame(main, bg=C_BG)
        bot.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        bot.rowconfigure(0, weight=1)
        for col in range(3):
            bot.columnconfigure(col, weight=1)

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

            bar = tk.Canvas(p, height=5, bg="#0a1a2e", highlightthickness=0)
            bar.grid(row=2, column=0, sticky="ew", padx=7, pady=(0, 6))

            self._metric_widgets.append((title_lbl, val_lbl, bar))

    def _build_codes(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._codes_frame = f

        # Status bar (amber, matches 30px style of other screens)
        bar = tk.Frame(f, bg="#000a14", height=30)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="⚠", font=(_FF, 10), bg="#000a14", fg=C_WARN).pack(
            side="left", padx=(10, 2)
        )
        tk.Label(bar, text="FAULT CODES DETECTED", font=(_FF, 9), bg="#000a14", fg=C_WARN).pack(
            side="left"
        )
        self._codes_clock = tk.Label(bar, text="", font=(_FF, 9), bg="#000a14", fg=C_TEXT_SEC)
        self._codes_clock.pack(side="right", padx=10)

        # Column headers
        hdr = tk.Frame(f, bg=C_PANEL, height=24)
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="CODE", font=(_FF, 9, "bold"), bg=C_PANEL, fg=C_TEXT_SEC,
                 width=10, anchor="w").pack(side="left", padx=(10, 0))
        tk.Label(hdr, text="DESCRIPTION", font=(_FF, 9, "bold"), bg=C_PANEL, fg=C_TEXT_SEC,
                 anchor="w").pack(side="left", padx=(6, 0))

        # Scrollable code list
        list_container = tk.Frame(f, bg=C_BG)
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 0))

        self._codes_canvas = tk.Canvas(list_container, bg=C_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical",
                                 command=self._codes_canvas.yview)
        self._codes_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._codes_canvas.pack(side="left", fill="both", expand=True)

        self._codes_list_frame = tk.Frame(self._codes_canvas, bg=C_BG)
        self._codes_canvas_window = self._codes_canvas.create_window(
            (0, 0), window=self._codes_list_frame, anchor="nw"
        )
        self._codes_list_frame.bind("<Configure>", self._on_codes_frame_configure)
        self._codes_canvas.bind("<Configure>", self._on_codes_canvas_configure)

        # Footer
        footer = tk.Label(
            f, text="Tap anywhere to return to live view",
            font=(_FF, 9), bg=C_BG, fg=C_TEXT_SEC,
        )
        footer.pack(pady=(3, 6))

        # Tap-to-dismiss bindings
        f.bind("<Button-1>", self._on_codes_tap)
        footer.bind("<Button-1>", self._on_codes_tap)
        self._codes_canvas.bind("<Button-1>", self._on_codes_tap)

    def _build_graph(self):
        f = tk.Frame(self.root, bg=C_BG)
        self._graph_frame = f

        # Status bar with BACK button
        bar = tk.Frame(f, bg="#000a14", height=30)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        back_btn = tk.Label(bar, text="  ◀ BACK  ", font=(_FF, 8, "bold"),
                            bg=C_BORDER, fg=C_TEXT_PRI)
        back_btn.pack(side="left", padx=(4, 0), fill="y")
        back_btn.bind("<Button-1>", self._on_graph_back)

        self._graph_title = tk.Label(bar, text="", font=(_FF, 9, "bold"),
                                      bg="#000a14", fg=C_TEXT_PRI)
        self._graph_title.pack(side="left", padx=14)

        self._graph_clock = tk.Label(bar, text="", font=(_FF, 9),
                                      bg="#000a14", fg=C_TEXT_SEC)
        self._graph_clock.pack(side="right", padx=10)

        # Metric selector row (bottom)
        sel = tk.Frame(f, bg="#000a14", height=36)
        sel.pack(fill="x", side="bottom")
        sel.pack_propagate(False)

        self._graph_btns = []
        for i, (key, label, unit, y_min, y_max, color, _ext) in enumerate(GRAPH_METRICS):
            btn = tk.Label(sel, text=label, font=(_FF, 8, "bold"),
                           bg=C_PANEL, fg=C_TEXT_SEC)
            btn.pack(side="left", fill="both", expand=True,
                     padx=(0 if i == 0 else 1, 0), pady=2)
            btn.bind("<Button-1>", lambda e, idx=i: self._select_graph_metric(idx))
            self._graph_btns.append(btn)

        # Chart canvas (fills remaining space)
        self._graph_canvas = tk.Canvas(f, bg=C_BG, highlightthickness=0)
        self._graph_canvas.pack(fill="both", expand=True)
        self._graph_canvas.bind("<Button-1>", self._on_graph_canvas_tap)

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

    def show_live(self, data: dict, history: list, dtcs_empty: bool = False) -> None:
        self._live_data = data
        self._last_history = history
        self._live_codes_lbl.config(
            text="  ✓ NO CODES" if dtcs_empty else ""
        )
        if self._graph_mode:
            if self._screen != "graph":
                self._hide_all()
                self._graph_frame.pack(fill="both", expand=True)
                self._screen = "graph"
                self._select_graph_metric(self._graph_metric_idx)
            self._refresh_graph(history)
        else:
            if self._screen != "live":
                self._hide_all()
                self._live_frame.pack(fill="both", expand=True)
                self._screen = "live"
                self._start_rotation()
            self._refresh_live(data)

    def show_codes(self, dtcs: list) -> None:
        if self._screen != "codes":
            self._hide_all()
            self._codes_frame.pack(fill="both", expand=True)
            self._screen = "codes"
            self._last_dtcs_rendered = []   # force rebuild on first show

        if dtcs == self._last_dtcs_rendered:
            return   # nothing changed, skip rebuild
        self._last_dtcs_rendered = list(dtcs)

        for widget in self._codes_list_frame.winfo_children():
            widget.destroy()

        for i, (code, desc) in enumerate(dtcs):
            row_bg = C_PANEL if i % 2 == 0 else C_BG
            row = tk.Frame(self._codes_list_frame, bg=row_bg, height=36)
            row.pack(fill="x")
            row.pack_propagate(False)
            code_lbl = tk.Label(row, text=code, font=(_FF, 11, "bold"), bg=row_bg,
                                fg=C_WARN, width=10, anchor="w")
            code_lbl.pack(side="left", padx=(10, 0))
            desc_lbl = tk.Label(row, text=desc, font=(_FF, 10), bg=row_bg,
                                fg=C_TEXT_PRI, anchor="w", wraplength=300)
            desc_lbl.pack(side="left", padx=(6, 0))
            row.bind("<Button-1>", self._on_codes_tap)
            code_lbl.bind("<Button-1>", self._on_codes_tap)
            desc_lbl.bind("<Button-1>", self._on_codes_tap)

        if not dtcs:
            tk.Label(
                self._codes_list_frame,
                text="No fault codes stored.",
                font=(_FF, 11), bg=C_BG, fg=C_TEXT_DIM,
            ).pack(pady=14)

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
        for frame in (self._disc_frame, self._wait_frame, self._live_frame,
                      self._codes_frame, self._graph_frame):
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
        ring_c = C_CRIT if bright else "#001a3a"
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
        b = int(0x33 + (0xcc - 0x33) * (1.0 - t))
        color = f"#0044{b:02x}"
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

    # ── Codes screen helpers ───────────────────────────────────────────────────

    def _on_codes_tap(self, event=None):
        if self.dismiss_codes:
            self.dismiss_codes()

    def _on_codes_frame_configure(self, event=None):
        self._codes_canvas.configure(scrollregion=self._codes_canvas.bbox("all"))

    def _on_codes_canvas_configure(self, event=None):
        self._codes_canvas.itemconfig(self._codes_canvas_window, width=event.width)

    # ── Graph handlers ─────────────────────────────────────────────────────────

    def _on_graph_btn(self, _event=None) -> None:
        self._graph_mode = True
        self._hide_all()
        self._graph_frame.pack(fill="both", expand=True)
        self._screen = "graph"
        self._select_graph_metric(self._graph_metric_idx)
        self._refresh_graph(self._last_history)

    def _on_graph_back(self, _event=None) -> None:
        self._graph_mode = False
        self._hide_all()
        self._live_frame.pack(fill="both", expand=True)
        self._screen = "live"
        self._start_rotation()
        self._refresh_live(self._live_data)

    def _on_graph_canvas_tap(self, _event=None) -> None:
        self._select_graph_metric((self._graph_metric_idx + 1) % len(GRAPH_METRICS))

    def _select_graph_metric(self, idx: int) -> None:
        self._graph_metric_idx = idx
        _, label, *_ = GRAPH_METRICS[idx]
        self._graph_title.config(text=label)
        for i, btn in enumerate(self._graph_btns):
            btn.config(
                bg=C_BORDER if i == idx else C_PANEL,
                fg=C_TEXT_PRI if i == idx else C_TEXT_SEC,
            )
        self._refresh_graph(self._last_history)

    def _refresh_graph(self, history: list) -> None:
        canvas = self._graph_canvas
        canvas.update_idletasks()
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10 or h < 10:
            self.root.after(100, lambda: self._refresh_graph(history))
            return

        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, h, fill=C_BG, outline="")

        key, label, unit, y_min, y_max, color, extractor = GRAPH_METRICS[self._graph_metric_idx]

        # Extract numeric values from history snapshots
        values = []
        for snapshot in history:
            raw = snapshot.get(key)
            if raw is None:
                values.append(None)
            else:
                try:
                    values.append(extractor(raw))
                except Exception:
                    values.append(None)

        valid = [v for v in values if v is not None]
        if not valid:
            canvas.create_text(w // 2, h // 2,
                               text="No data for this metric yet",
                               font=(_FF, 12), fill=C_TEXT_DIM)
            return

        # Dynamic Y range clamped to metric limits
        spread = max(valid) - min(valid)
        margin = max(spread * 0.1, 1)
        y_lo = max(y_min, min(valid) - margin)
        y_hi = min(y_max, max(valid) + margin)
        if y_hi - y_lo < 1:
            mid = (y_lo + y_hi) / 2
            y_lo, y_hi = mid - 0.5, mid + 0.5

        pad_l, pad_r, pad_t, pad_b = 46, 12, 12, 20
        cw = w - pad_l - pad_r
        ch = h - pad_t - pad_b

        # Chart background
        canvas.create_rectangle(pad_l, pad_t, pad_l + cw, pad_t + ch,
                                 fill=C_PANEL, outline=C_BORDER)

        # Horizontal gridlines + Y labels
        for i in range(5):
            frac = i / 4
            y_val = y_lo + (y_hi - y_lo) * frac
            y_px = pad_t + ch - int(ch * frac)
            canvas.create_line(pad_l, y_px, pad_l + cw, y_px,
                               fill=C_BORDER, width=1)
            canvas.create_text(pad_l - 3, y_px, text=f"{y_val:.0f}",
                               font=(_FF, 7), fill=C_TEXT_DIM, anchor="e")

        # Time axis labels
        canvas.create_text(pad_l + 2, pad_t + ch + 9,
                           text="← older", font=(_FF, 7), fill=C_TEXT_DIM, anchor="w")
        canvas.create_text(pad_l + cw - 2, pad_t + ch + 9,
                           text="now →", font=(_FF, 7), fill=C_TEXT_DIM, anchor="e")

        # Data line
        n = len(values)
        coords = []
        for i, v in enumerate(values):
            if v is None:
                continue
            x = pad_l + int(cw * i / max(n - 1, 1))
            frac_y = (max(y_lo, min(y_hi, v)) - y_lo) / (y_hi - y_lo)
            y = pad_t + ch - int(ch * frac_y)
            coords.extend([x, y])
        if len(coords) >= 4:
            canvas.create_line(coords, fill=color, width=2,
                               capstyle="round", joinstyle="round")

        # Current value overlay (top-right of chart)
        canvas.create_text(pad_l + cw - 4, pad_t + 6,
                           text=f"{valid[-1]:.0f} {unit}",
                           font=(_FF, 18, "bold"), fill=color, anchor="ne")

        # Metric label (top-left of chart)
        canvas.create_text(pad_l + 4, pad_t + 6,
                           text=label, font=(_FF, 8), fill=C_TEXT_SEC, anchor="nw")

    # ── Clock ──────────────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self._wait_clock.config(text=now)
        self._live_clock.config(text=now)
        self._codes_clock.config(text=now)
        self._graph_clock.config(text=now)
        self.root.after(1000, self._tick_clock)
