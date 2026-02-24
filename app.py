# app.py
import time
import tkinter as tk

from config import BLUETOOTH_RFCOMM_DEVICE, UPDATE_HZ
from obd_service import OBDService
from ui_tk import DashboardUI

def main():
    root = tk.Tk()
    ui = DashboardUI(root)

    obd_svc = OBDService(BLUETOOTH_RFCOMM_DEVICE)
    interval_ms = int(1000 / UPDATE_HZ)

    def tick():
        ok = obd_svc.ensure_connected()
        if not ok:
            ui.set_status("OBD: disconnected (retrying)")
            ui.update_values({})
            root.after(1000, tick)
            return

        ui.set_status("OBD: connected")
        data = obd_svc.read_snapshot()
        ui.update_values(data)

        root.after(interval_ms, tick)

    # slight delay so UI paints
    root.after(250, tick)
    root.mainloop()

if __name__ == "__main__":
    main()