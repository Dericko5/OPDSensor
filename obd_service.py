# obd_service.py  –  Vehicle communication layer (OBD-II via ELM327 / RFCOMM)

import obd


class OBDService:
    """
    Abstracts all OBD-II communication.

    Designed to run in a background thread.  The only shared state is the
    dict returned by read_snapshot(); values are immutable pint Quantities
    so they are safe to hand off to the UI thread without extra locking.
    """

    # PIDs queried on every poll cycle.
    # Add / remove entries here to change what is monitored.
    _CMDS = {
        "rpm":          obd.commands.RPM,
        "speed":        obd.commands.SPEED,
        "coolant_temp": obd.commands.COOLANT_TEMP,
        "throttle_pos": obd.commands.THROTTLE_POS,
        "engine_load":  obd.commands.ENGINE_LOAD,
    }

    def __init__(self, port: str):
        self.port = port
        self.connection = None

    # ── Connection management ──────────────────────────────────────────────────

    def connect(self) -> bool:
        """Open a new OBD connection. Returns True on success."""
        try:
            # fast=False: more compatible with cheap ELM327 clones.
            # timeout=5: avoid hanging forever if the adapter is present but
            #            the car ECU is not responding.
            self.connection = obd.OBD(portstr=self.port, fast=False, timeout=5)
            return self.connection.is_connected()
        except Exception:
            self.connection = None
            return False

    def disconnect(self):
        """Close the current connection (ignores errors)."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None

    def ensure_connected(self) -> bool:
        """
        Check the current connection; attempt one reconnect if needed.
        Does NOT sleep – the caller is responsible for retry delays.
        """
        if self.connection and self.connection.is_connected():
            return True
        self.disconnect()
        return self.connect()

    # ── Data acquisition ───────────────────────────────────────────────────────

    def _safe_query(self, cmd):
        """Query a single PID; returns None on any failure or null response."""
        try:
            r = self.connection.query(cmd)
            return None if r.is_null() else r.value
        except Exception:
            return None

    def read_snapshot(self) -> dict:
        """
        Query all configured PIDs in one pass.
        Returns a dict keyed by name; values are pint Quantities or None.
        """
        if not self.connection or not self.connection.is_connected():
            return {k: None for k in self._CMDS}
        return {key: self._safe_query(cmd) for key, cmd in self._CMDS.items()}
