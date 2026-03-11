# app.py  –  Application controller (entry point)
#
# Architecture:
#   ┌────────────────────────┐      shared lock
#   │  OBD background thread │ ──────────────────────────────────────────────┐
#   │  (obd_worker)          │  writes _state / _data                        │
#   └────────────────────────┘                                                │
#                                                                             ▼
#   ┌────────────────────────┐      reads _state / _data every UI_REFRESH_HZ │
#   │  Tkinter main thread   │ ◄─────────────────────────────────────────────┘
#   │  (_ui_tick via after() │  calls ui.show_disconnected / waiting / live()
#   └────────────────────────┘
#
# This design keeps all OBD I/O (including blocking connect/sleep calls) off
# the main thread so the UI stays responsive during connection attempts.

import threading
import time
import tkinter as tk

from config import (
    OBD_DEVICE,
    OBD_POLL_HZ, UI_REFRESH_HZ, RECONNECT_DELAY_S,
    LOG_ENABLED,
)
from obd_service import OBDService
from ui_tk import DashboardUI
from logger import DataLogger


class AppController:
    def __init__(self):
        self.root = tk.Tk()
        self.ui   = DashboardUI(self.root)
        self.ui.dismiss_codes = self._on_dismiss_codes
        self.obd  = OBDService(OBD_DEVICE)
        self.logger = DataLogger() if LOG_ENABLED else None

        # Shared state (protected by _lock)
        self._state: str = "disconnected"   # "disconnected" | "waiting" | "live" | "codes"
        self._data:  dict = {}
        self._dtcs:  list = []
        self._lock = threading.Lock()
        self._running = True

        # UI-thread-only dismissal state (no lock needed)
        self._dtc_dismissed: bool = False
        self._dtc_dismissed_set: set = set()

        # Start background OBD thread (daemon: killed automatically on exit)
        self._thread = threading.Thread(target=self._obd_worker, daemon=True)
        self._thread.start()

        # Kick off the UI refresh loop
        self.root.after(200, self._ui_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── OBD background thread ──────────────────────────────────────────────────

    def _obd_worker(self) -> None:
        poll_interval = 1.0 / OBD_POLL_HZ
        _dtc_poll_counter = 0

        while self._running:
            # ── Step 1: ensure connection ──────────────────────────────────────
            connected = self.obd.ensure_connected()

            if not connected:
                with self._lock:
                    self._state = "disconnected"
                    self._data  = {}
                    self._dtcs  = []
                # Wait before retrying so we don't hammer the USB port
                time.sleep(RECONNECT_DELAY_S)
                continue

            # ── Step 2: read a snapshot from the ECU ──────────────────────────
            snapshot = self.obd.read_snapshot()
            has_data = any(v is not None for v in snapshot.values())

            # ── Step 3: poll DTCs every 10 cycles (~5 s at 2 Hz) ──────────────
            _dtc_poll_counter += 1
            new_dtcs = None
            if _dtc_poll_counter >= 10:
                _dtc_poll_counter = 0
                new_dtcs = self.obd.read_dtcs()

            with self._lock:
                if new_dtcs is not None:
                    self._dtcs = new_dtcs
                if has_data and self._dtcs:
                    self._state = "codes"
                elif has_data:
                    self._state = "live"
                else:
                    self._state = "waiting"
                self._data = snapshot

            # ── Step 4: log if we have real data ──────────────────────────────
            if has_data and self.logger:
                try:
                    self.logger.log(snapshot)
                except Exception:
                    pass   # never let logging crash the OBD loop

            time.sleep(poll_interval)

    # ── UI refresh (main thread) ───────────────────────────────────────────────

    def _ui_tick(self) -> None:
        with self._lock:
            state = self._state
            data  = dict(self._data)   # shallow copy is safe; Quantities are immutable
            dtcs  = list(self._dtcs)

        if state == "disconnected":
            self.ui.show_disconnected()
        elif state == "waiting":
            self.ui.show_waiting()
        elif state == "codes":
            current_codes = set(c for c, _ in dtcs)
            if self._dtc_dismissed and current_codes == self._dtc_dismissed_set:
                self.ui.show_live(data)
            else:
                if self._dtc_dismissed and current_codes != self._dtc_dismissed_set:
                    self._dtc_dismissed = False
                    self._dtc_dismissed_set = set()
                self.ui.show_codes(dtcs)
        else:
            self._dtc_dismissed = False
            self.ui.show_live(data)

        self.root.after(int(1000 / UI_REFRESH_HZ), self._ui_tick)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _on_dismiss_codes(self) -> None:
        """Called by the UI when the user taps the codes screen."""
        self._dtc_dismissed = True
        with self._lock:
            self._dtc_dismissed_set = set(c for c, _ in self._dtcs)

    def _on_close(self) -> None:
        self._running = False
        self.obd.disconnect()
        if self.logger:
            self.logger.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = AppController()
    app.run()


if __name__ == "__main__":
    main()
