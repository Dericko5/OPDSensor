# obd_service.py
import time
import obd

class OBDService:
    def __init__(self, port: str):
        self.port = port
        self.connection = None

        # Pick a useful set of PIDs (supported depends on car)
        self.cmd_rpm = obd.commands.RPM
        self.cmd_speed = obd.commands.SPEED
        self.cmd_coolant = obd.commands.COOLANT_TEMP
        self.cmd_throttle = obd.commands.THROTTLE_POS
        self.cmd_load = obd.commands.ENGINE_LOAD

    def connect(self) -> bool:
        try:
            # fast=False is more compatible; start simple
            self.connection = obd.OBD(portstr=self.port, fast=False)
            return self.connection.is_connected()
        except Exception:
            self.connection = None
            return False

    def disconnect(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None

    def safe_query(self, cmd):
        if not self.connection or not self.connection.is_connected():
            return None
        try:
            r = self.connection.query(cmd)
            if r.is_null():
                return None
            return r.value
        except Exception:
            return None

    def read_snapshot(self) -> dict:
        """Return a dict of current readings (raw units from python-OBD)."""
        return {
            "rpm": self.safe_query(self.cmd_rpm),
            "speed": self.safe_query(self.cmd_speed),
            "coolant_temp": self.safe_query(self.cmd_coolant),
            "throttle_pos": self.safe_query(self.cmd_throttle),
            "engine_load": self.safe_query(self.cmd_load),
        }

    def ensure_connected(self, retry_seconds=2) -> bool:
        if self.connection and self.connection.is_connected():
            return True
        self.disconnect()
        ok = self.connect()
        if not ok:
            time.sleep(retry_seconds)
        return ok