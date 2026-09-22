"""Conservative, sampled observations for the private MaiaVision dashboard.

This is NOT animal identification, emotion recognition, physical speed, or a
continuous activity tracker. Samples from overlapping cameras are not summed.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_INTERVAL_SECONDS = 10
RETENTION_SECONDS = 7 * 24 * 3600
VISIBLE = ("SIN REFERENCIA", "QUIETA", "MOVIMIENTO")
EVALUABLE = ("QUIETA", "MOVIMIENTO")


def iso_utc(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds") if value is not None else None


class InsightsStore:
    """Persist a small metadata sample per camera, never a frame or video."""

    def __init__(self, database: str) -> None:
        self.database = database
        self.lock = threading.Lock()
        self.last_sample: dict[str, int] = {}
        self.last_prune = 0

    def init(self) -> None:
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS activity_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                camera_id TEXT NOT NULL,
                status TEXT NOT NULL
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_samples(timestamp)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_activity_camera_time ON activity_samples(camera_id,timestamp)")

    def record(self, camera_id: str, status: str, *, now: int | None = None) -> None:
        if status == "SIN ANALISIS":
            return  # --no-vision: a camera feed is not a dog observation.
        timestamp = int(time.time()) if now is None else now
        with self.lock:
            if timestamp - self.last_sample.get(camera_id, -RETENTION_SECONDS) < SAMPLE_INTERVAL_SECONDS:
                return
            with sqlite3.connect(self.database) as connection:
                connection.execute("INSERT INTO activity_samples(timestamp,camera_id,status) VALUES (?,?,?)",
                                   (timestamp, camera_id, status))
                if timestamp - self.last_prune >= 3600:
                    connection.execute("DELETE FROM activity_samples WHERE timestamp < ?",
                                       (timestamp - RETENTION_SECONDS,))
                    self.last_prune = timestamp
            self.last_sample[camera_id] = timestamp

    def summary(self, cameras: dict[str, str], window_minutes: int, *, now: int | None = None) -> dict:
        timestamp = int(time.time()) if now is None else now
        cutoff = timestamp - window_minutes * 60
        counts = {camera_id: {"observed_samples": 0, "visible_samples": 0,
                              "evaluable_samples": 0, "moving_samples": 0}
                  for camera_id in cameras}
        last_seen: dict[str, int] = {}
        last_detection: dict | None = None
        with self.lock, sqlite3.connect(self.database) as connection:
            for camera_id, total, visible, evaluable, moving in connection.execute("""
                SELECT camera_id, COUNT(*),
                    SUM(CASE WHEN status IN ('SIN REFERENCIA','QUIETA','MOVIMIENTO') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status IN ('QUIETA','MOVIMIENTO') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 'MOVIMIENTO' THEN 1 ELSE 0 END)
                FROM activity_samples WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY camera_id
            """, (cutoff, timestamp)):
                if camera_id in counts:
                    counts[camera_id] = {"observed_samples": total, "visible_samples": visible,
                                         "evaluable_samples": evaluable, "moving_samples": moving}
            for camera_id, seen in connection.execute("""
                SELECT camera_id, MAX(timestamp) FROM activity_samples
                WHERE status IN ('SIN REFERENCIA','QUIETA','MOVIMIENTO') AND timestamp >= ? AND timestamp <= ?
                GROUP BY camera_id
            """, (timestamp - RETENTION_SECONDS, timestamp)):
                last_seen[camera_id] = seen
            row = connection.execute("""
                SELECT camera_id,timestamp FROM activity_samples
                WHERE status IN ('SIN REFERENCIA','QUIETA','MOVIMIENTO') AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC,id DESC LIMIT 1
            """, (timestamp - RETENTION_SECONDS, timestamp)).fetchone()
            if row and row[0] in cameras:
                last_detection = {"camera_id": row[0], "camera_name": cameras[row[0]],
                                  "timestamp": iso_utc(row[1])}
        entries = []
        for camera_id, name in cameras.items():
            values = counts[camera_id]
            evaluable = values["evaluable_samples"]
            entries.append({"camera_id": camera_id, "camera_name": name, **values,
                            "activity_percent": round(100 * values["moving_samples"] / evaluable)
                            if evaluable else None,
                            "last_seen_at": iso_utc(last_seen.get(camera_id))})
        return {"window_minutes": window_minutes,
                "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
                "last_detection": last_detection,
                "cameras": entries}
