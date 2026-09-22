"""Bounded, in-memory PTZ commands: browser -> authenticated API -> LAN edge.

The VPS never connects to a private camera IP and never stores ONVIF credentials.
Commands are short lived; no camera movements are replayed after an edge restart.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

DIRECTIONS = frozenset({"left", "right", "up", "down", "stop"})
HEARTBEAT_TTL = 8.0
COMMAND_TTL = 3.0
COOLDOWN = 0.18


@dataclass(frozen=True)
class Command:
    sequence: int
    direction: str
    created: float


class PtzMailbox:
    def __init__(self, camera_ids: set[str]) -> None:
        self.camera_ids = camera_ids
        self.lock = threading.Lock()
        self.last_seen: dict[str, float] = {}
        self.last_sent: dict[str, float] = {}
        self.commands: dict[str, list[Command]] = {camera_id: [] for camera_id in camera_ids}
        self.sequence: dict[str, int] = {camera_id: 0 for camera_id in camera_ids}

    def ready(self, camera_id: str) -> bool:
        with self.lock:
            return time.monotonic() - self.last_seen.get(camera_id, float('-inf')) < HEARTBEAT_TTL

    def poll(self, camera_id: str, since: int | None) -> dict:
        """A first poll registers availability but deliberately skips earlier commands."""
        with self.lock:
            now = time.monotonic()
            self.last_seen[camera_id] = now
            current = self.sequence[camera_id]
            self.commands[camera_id] = [command for command in self.commands[camera_id]
                                        if now - command.created <= COMMAND_TTL]
            if since is None:
                return {"sequence": current, "commands": []}
            return {"sequence": current,
                    "commands": [{"sequence": command.sequence, "direction": command.direction}
                                 for command in self.commands[camera_id] if command.sequence > since]}

    def send(self, camera_id: str, direction: str) -> int:
        if direction not in DIRECTIONS:
            raise ValueError("Dirección PTZ no válida")
        with self.lock:
            now = time.monotonic()
            if now - self.last_seen.get(camera_id, float('-inf')) >= HEARTBEAT_TTL:
                raise RuntimeError("El agente PTZ no está conectado")
            if direction != "stop" and now - self.last_sent.get(camera_id, float('-inf')) < COOLDOWN:
                raise BlockingIOError("Espera un instante entre movimientos")
            self.sequence[camera_id] += 1
            sequence = self.sequence[camera_id]
            # A stop supersedes queued movement; a late command is never executed after stop.
            if direction == "stop":
                self.commands[camera_id].clear()
            self.commands[camera_id].append(Command(sequence, direction, now))
            self.commands[camera_id] = self.commands[camera_id][-12:]
            self.last_sent[camera_id] = now
            return sequence
