# ui_tk.py
import tkinter as tk
from tkinter import ttk

class DashboardUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OBD Dashboard")
        self.root.attributes("-fullscreen", True)

        self.style = ttk.Style()
        self.style.configure("Big.TLabel", font=("DejaVu Sans", 28))
        self.style.configure("Huge.TLabel", font=("DejaVu Sans", 60, "bold"))

        self.speed_var = tk.StringVar(value="-- mph")
        self.rpm_var = tk.StringVar(value="---- rpm")
        self.coolant_var = tk.StringVar(value="-- °C")
        self.throttle_var = tk.StringVar(value="-- %")
        self.load_var = tk.StringVar(value="-- %")
        self.status_var = tk.StringVar(value="Connecting...")

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, textvariable=self.speed_var, style="Huge.TLabel").pack(anchor="w", pady=(0, 20))
        ttk.Label(frame, textvariable=self.rpm_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.coolant_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.throttle_var, style="Big.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.load_var, style="Big.TLabel").pack(anchor="w")

        ttk.Label(frame, textvariable=self.status_var, font=("DejaVu Sans", 16)).pack(anchor="w", pady=(30, 0))

        # Exit on ESC for debugging
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def set_status(self, s: str):
        self.status_var.set(s)

    def update_values(self, data: dict):
        # python-OBD values come in with units; handle None gracefully.
        speed = data.get("speed")
        rpm = data.get("rpm")
        coolant = data.get("coolant_temp")
        throttle = data.get("throttle_pos")
        load = data.get("engine_load")

        self.speed_var.set(f"{speed.to('mph').magnitude:.0f} mph" if speed else "-- mph")
        self.rpm_var.set(f"{rpm.magnitude:.0f} rpm" if rpm else "---- rpm")
        self.coolant_var.set(f"{coolant.to('degC').magnitude:.0f} °C" if coolant else "-- °C")
        self.throttle_var.set(f"{throttle.magnitude:.0f} %" if throttle else "-- %")
        self.load_var.set(f"{load.magnitude:.0f} %" if load else "-- %")