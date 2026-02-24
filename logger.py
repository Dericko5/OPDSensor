# logger.py  –  CSV telemetry logger

import csv
import os
import time

from config import LOG_CSV_PATH


class DataLogger:
    """
    Appends one row per snapshot to a CSV file.
    Creates the file and parent directories if they don't exist.
    Uses line-buffering so data survives an unexpected power cut.
    """

    _HEADER = [
        "timestamp",
        "speed_mph",
        "rpm",
        "coolant_c",
        "throttle_pct",
        "load_pct",
    ]

    def __init__(self):
        dir_name = os.path.dirname(LOG_CSV_PATH)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        is_new = (
            not os.path.exists(LOG_CSV_PATH)
            or os.path.getsize(LOG_CSV_PATH) == 0
        )
        # buffering=1 → line-buffered, flushes after every row
        self._file = open(LOG_CSV_PATH, "a", newline="", buffering=1)
        self._writer = csv.writer(self._file)
        if is_new:
            self._writer.writerow(self._HEADER)

    def log(self, data: dict):
        """Write one row. Values that failed to query are stored as empty strings."""
        speed   = data.get("speed")
        rpm     = data.get("rpm")
        coolant = data.get("coolant_temp")
        throttle = data.get("throttle_pos")
        load    = data.get("engine_load")

        self._writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{speed.to('mph').magnitude:.1f}"      if speed    else "",
            f"{rpm.magnitude:.0f}"                   if rpm      else "",
            f"{coolant.to('degC').magnitude:.1f}"   if coolant  else "",
            f"{throttle.magnitude:.1f}"              if throttle else "",
            f"{load.magnitude:.1f}"                  if load     else "",
        ])

    def close(self):
        self._file.close()
