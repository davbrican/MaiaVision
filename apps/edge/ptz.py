"""ONVIF PTZ runs exclusively on the LAN edge, never on the public VPS.

Only explicitly configured cameras accept commands. The optional ONVIF package is
imported lazily so webcams/Android streams keep working without it.
"""
from __future__ import annotations

import ipaddress
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
DIRECTIONS = {"left", "right", "up", "down", "stop"}
MOVE_SECONDS = 0.35
SETTLE_SECONDS = 3.0


@dataclass(frozen=True, repr=False)
class PtzConfig:
    host: str
    username: str
    password: str = field(repr=False)
    port: int = 2020
    invert_pan: bool = False
    invert_tilt: bool = False


def parse_ptz(value: object, camera_id: str) -> PtzConfig | None:
    """Resolve local-only ONVIF credentials from env; never persist in JSON/Git."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"host_env", "user_env", "password_env", "port", "invert_pan", "invert_tilt"}:
        raise ValueError(f"{camera_id}: configuración PTZ inválida")
    env_names = [value.get(key) for key in ("host_env", "user_env", "password_env")]
    if any(not isinstance(name, str) or not ENV_NAME.fullmatch(name) for name in env_names):
        raise ValueError(f"{camera_id}: variables PTZ inválidas")
    host, username, password = (os.getenv(name, "") for name in env_names)
    if not host or not username or not password:
        raise ValueError(f"{camera_id}: faltan MAIA_* de host/usuario/contraseña PTZ")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(f"{camera_id}: PTZ requiere IP privada literal, no dominio ni URL") from exc
    if not isinstance(ip, ipaddress.IPv4Address) or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        raise ValueError(f"{camera_id}: PTZ requiere IPv4 de LAN privada")
    port = value.get("port", 2020)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError(f"{camera_id}: puerto PTZ inválido")
    invert_pan = value.get("invert_pan", False)
    invert_tilt = value.get("invert_tilt", False)
    if type(invert_pan) is not bool or type(invert_tilt) is not bool:
        raise ValueError(f"{camera_id}: inversión PTZ debe ser booleana")
    return PtzConfig(str(ip), username, password, port, invert_pan, invert_tilt)


def direction_velocity(direction: str, settings: PtzConfig) -> tuple[float, float]:
    if direction not in DIRECTIONS:
        raise ValueError("Dirección PTZ inválida")
    vectors = {"left": (-0.35, 0.0), "right": (0.35, 0.0),
               "up": (0.0, 0.35), "down": (0.0, -0.35), "stop": (0.0, 0.0)}
    pan, tilt = vectors[direction]
    return (-pan if settings.invert_pan else pan,
            -tilt if settings.invert_tilt else tilt)


class OnvifPtz:
    """Short bounded moves with unconditional Stop, including exceptional paths."""
    def __init__(self, settings: PtzConfig) -> None:
        from onvif import ONVIFCamera  # optional: pip install -r apps/edge/requirements-ptz.txt

        self.settings = settings
        camera = ONVIFCamera(settings.host, settings.port, settings.username, settings.password)
        media = camera.create_media_service()
        profiles = media.GetProfiles()
        profile = next((profile for profile in profiles if getattr(profile, "PTZConfiguration", None)), None)
        if profile is None:
            raise RuntimeError("La cámara no anuncia un perfil ONVIF PTZ")
        self.token = getattr(profile, "token", None) or getattr(profile, "_token", None)
        if not self.token:
            raise RuntimeError("Perfil ONVIF sin token")
        self.service = camera.create_ptz_service()
        # Reject unsupported ContinuousMove rather than pretending physical movement works.
        options = self.service.GetConfigurationOptions({"ConfigurationToken": profile.PTZConfiguration.token})
        spaces = getattr(getattr(options, "Spaces", None), "ContinuousPanTiltVelocitySpace", None)
        if not spaces:
            raise RuntimeError("La cámara no anuncia movimiento continuo PTZ")
        self.speed_space = spaces[0].URI

    def stop(self) -> None:
        self.service.Stop({"ProfileToken": self.token, "PanTilt": True})

    def execute(self, direction: str) -> None:
        if direction == "stop":
            self.stop()
            return
        pan, tilt = direction_velocity(direction, self.settings)
        try:
            self.service.ContinuousMove({
                "ProfileToken": self.token,
                "Velocity": {"PanTilt": {"x": pan, "y": tilt, "space": self.speed_space}},
                "Timeout": "PT1S",  # Firmware safety fallback if edge disconnects mid-motion.
            })
            time.sleep(MOVE_SECONDS)
        finally:
            self.stop()


def run_ptz(camera_id: str, settings: PtzConfig, backend: str, token: str,
            pause_until: dict[str, float], stop: threading.Event) -> None:
    """One independent polling loop per PTZ camera; video threads never block."""
    import requests

    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + token})
    url = f"{backend}/api/edge/{camera_id}/ptz/commands"
    try:
        while not stop.is_set():
            try:
                controller = OnvifPtz(settings)
            except ImportError:
                print(f"[{camera_id}] PTZ no disponible: instala apps/edge/requirements-ptz.txt", file=sys.stderr)
                return
            except Exception as exc:
                # No exception message: some ONVIF clients interpolate credentials/addresses.
                print(f"[{camera_id}] PTZ no disponible ({type(exc).__name__}); reintentando", file=sys.stderr)
                stop.wait(10)
                continue
            since: int | None = None
            print(f"[{camera_id}] Control ONVIF PTZ conectado")
            while not stop.is_set():
                try:
                    response = session.get(url, params={} if since is None else {"since": since}, timeout=5)
                    if response.status_code in (401, 404):
                        print(f"[{camera_id}] PTZ: token o ID incorrecto", file=sys.stderr)
                        return
                    response.raise_for_status()
                    message: dict[str, Any] = response.json()
                    # Process just the newest command, never a backlog of delayed movements.
                    commands = message.get("commands", [])
                    since = int(message["sequence"])
                    if commands:
                        direction = commands[-1]["direction"]
                        if direction not in DIRECTIONS:
                            continue
                        pause_until[camera_id] = time.monotonic() + MOVE_SECONDS + SETTLE_SECONDS
                        try:
                            controller.execute(direction)
                        except Exception as exc:
                            print(f"[{camera_id}] Error de control PTZ ({type(exc).__name__})", file=sys.stderr)
                            break  # Reinitialize ONVIF session; Stop attempted in execute().
                    stop.wait(0.45)
                except (requests.RequestException, ValueError, KeyError, TypeError):
                    print(f"[{camera_id}] PTZ: fallo de comunicación, reintentando", file=sys.stderr)
                    stop.wait(2)
            try:
                controller.stop()
            except Exception:
                pass
            stop.wait(2)
    finally:
        session.close()
