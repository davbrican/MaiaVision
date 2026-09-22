"""Multi-camera edge client: webcam, Android MJPEG/RTSP, IP RTSP and test files.

All camera URLs, ONVIF credentials and edge token stay on the LAN device;
only bounded JPEG previews and discrete observations go to the API.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from apps.edge.ptz import PtzConfig, parse_ptz, run_ptz
from maia_vision.activity import ActivityTracker

CAMERA_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
ROTATIONS = (0, 90, 180, 270)


@dataclass(frozen=True)
class Source:
    camera_id: str
    name: str
    kind: str
    value: int | str
    rotation: int = 0
    ptz: PtzConfig | None = None


def load_sources(path: Path) -> list[Source]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cameras"), list):
        raise ValueError("Configuración: se espera un objeto con lista 'cameras'")
    sources: list[Source] = []
    ids: set[str] = set()
    for camera in data["cameras"]:
        if not isinstance(camera, dict):
            raise ValueError("Cada cámara debe ser un objeto JSON")
        camera_id = camera.get("id")
        kind = camera.get("type")
        name = camera.get("name", camera_id)
        if not isinstance(camera_id, str) or not CAMERA_ID.fullmatch(camera_id) or camera_id in ids:
            raise ValueError("ID de cámara duplicado o inválido")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError(f"{camera_id}: nombre inválido")
        rotation = camera.get("rotation", 0)
        if type(rotation) is not int or rotation not in ROTATIONS:
            raise ValueError(f"{camera_id}: rotation debe ser 0, 90, 180 o 270")
        if kind == "webcam":
            value = camera.get("device", 0)
            if type(value) is not int or value < 0:
                raise ValueError("webcam.device debe ser un entero >= 0")
        elif kind in {"android", "rtsp", "mjpeg", "file"}:
            env_name = camera.get("source_env", "")
            if not isinstance(env_name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_name):
                raise ValueError(f"{camera_id}: source_env inválida")
            value = os.getenv(env_name, "")
            if not value:
                raise ValueError(f"Falta variable {env_name} para {camera_id}")
            if kind != "file" and urlparse(value).scheme not in ("http", "https", "rtsp", "rtsps"):
                raise ValueError(f"{camera_id}: URL HTTP(S) o RTSP(S) requerida")
            if kind == "file" and not Path(value).is_file():
                raise ValueError(f"{camera_id}: archivo de prueba no encontrado")
        else:
            raise ValueError(f"{camera_id}: tipo de cámara no admitido: {kind}")
        if "ptz" in camera and kind != "rtsp":
            raise ValueError(f"{camera_id}: PTZ ONVIF solo se admite en fuente RTSP")
        ptz = parse_ptz(camera.get("ptz"), camera_id)
        ids.add(camera_id)
        sources.append(Source(camera_id, name, kind, value, rotation, ptz))
    if not 1 <= len(sources) <= 12:
        raise ValueError("Configura entre 1 y 12 cámaras")
    return sources


def backend_address(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return value.rstrip("/")
    raise ValueError("El backend remoto requiere HTTPS; HTTP solo se permite en localhost")


def rotate_frame(frame: object, rotation: int) -> object:
    """Correct orientation before detection, annotation, encoding and snapshots."""
    if rotation == 0:
        return frame
    import cv2
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
             270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    return cv2.rotate(frame, codes[rotation])


def run_camera(source: Source, backend: str, token: str, fps: float, width: int,
               detector: object | None, detector_lock: threading.Lock,
               stop: threading.Event, pause_until: dict[str, float] | None = None) -> None:
    import cv2
    import requests

    tracker = ActivityTracker()
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + token, "Content-Type": "image/jpeg"})
    address = f"{backend}/api/edge/{source.camera_id}/frame"
    while not stop.is_set():
        capture = cv2.VideoCapture(source.value)
        if not capture.isOpened():
            print(f"[{source.camera_id}] Sin señal; reintentando", file=sys.stderr)
            capture.release()
            if source.kind == "file":
                break
            stop.wait(3)
            continue
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print(f"[{source.camera_id}] Fuente conectada ({source.kind})")
        tracker = ActivityTracker()  # Reconnecting must not create false motion events.
        try:
            next_frame = 0.0
            while not stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    break
                now = time.monotonic()
                if now < next_frame:
                    continue
                next_frame = now + 1.0 / fps
                frame = rotate_frame(frame, source.rotation)
                h, w = frame.shape[:2]
                if w > width:
                    frame = cv2.resize(frame, (width, round(h * width / w)))
                status = "SIN ANALISIS"
                event = None
                moving_camera = now < (pause_until or {}).get(source.camera_id, 0.0)
                if moving_camera:
                    tracker = ActivityTracker()  # Do not interpret camera movement as dog movement.
                elif detector is not None:
                    with detector_lock:
                        detection = detector.detect(frame)
                    observation = tracker.observe(detection.center if detection else None, now,
                                                  detection.confidence if detection else None)
                    status, event = observation.status, observation.event
                    if detection is not None:
                        cv2.rectangle(frame, (detection.x1, detection.y1),
                                      (detection.x2, detection.y2), (45, 205, 95), 2)
                label = "PTZ: ESTABILIZANDO" if moving_camera else status
                cv2.putText(frame, f"{source.name}: {label}", (12, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (45, 205, 95), 2)
                success, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if not success:
                    continue
                jpeg = image.tobytes()
                if len(jpeg) > 500_000:
                    print(f"[{source.camera_id}] Fotograma demasiado grande; reduce --width", file=sys.stderr)
                    continue
                headers = {"X-Maia-Status": status}
                if event:
                    headers["X-Maia-Event"] = event
                try:
                    response = session.post(address, data=jpeg, headers=headers, timeout=5)
                    if response.status_code in (401, 404):
                        print(f"[{source.camera_id}] Error HTTP {response.status_code}: revisa token/ID", file=sys.stderr)
                        stop.set()
                        break
                    response.raise_for_status()
                except requests.RequestException as exc:
                    print(f"[{source.camera_id}] No se pudo enviar el fotograma: {type(exc).__name__}", file=sys.stderr)
                    stop.wait(2)
        finally:
            capture.release()
        if source.kind == "file":
            break
        if not stop.is_set():
            print(f"[{source.camera_id}] Señal perdida, reconectando...", file=sys.stderr)
            stop.wait(3)
    session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="MaiaVision: agente de cámaras local")
    parser.add_argument("--config", type=Path, default=Path("config/cameras.mac.json"))
    parser.add_argument("--backend", default=os.getenv("MAIA_BACKEND_URL", "http://localhost:8080"))
    parser.add_argument("--fps", type=float, default=2.0, help="FPS por cámara (1-5 recomendado)")
    parser.add_argument("--width", type=int, default=640, help="Anchura máxima del JPEG")
    parser.add_argument("--model", default="yolo26n.pt")
    parser.add_argument("--no-vision", action="store_true", help="Solo vídeo; no cargar YOLO")
    args = parser.parse_args()
    if not 0 < args.fps <= 10 or not 160 <= args.width <= 1280:
        parser.error("--fps debe estar entre 0 y 10; --width entre 160 y 1280")
    try:
        sources = load_sources(args.config)
        backend = backend_address(args.backend)
        token = os.getenv("MAIA_EDGE_TOKEN", "")
        if len(token) < 32:
            raise ValueError("Define MAIA_EDGE_TOKEN (mínimo 32 caracteres) en el entorno")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    detector = None
    if not args.no_vision:
        from maia_vision.detector import DogDetector
        print("Cargando YOLO; primera ejecución puede descargar los pesos...")
        detector = DogDetector(model_path=args.model)
    stop = threading.Event()
    detector_lock = threading.Lock()
    pause_until: dict[str, float] = {}
    video_threads = [threading.Thread(target=run_camera, name=source.camera_id,
                     args=(source, backend, token, args.fps, args.width, detector, detector_lock, stop, pause_until),
                     daemon=True) for source in sources]
    ptz_threads = [threading.Thread(target=run_ptz, name="ptz-" + source.camera_id,
                   args=(source.camera_id, source.ptz, backend, token, pause_until, stop), daemon=True)
                   for source in sources if source.ptz is not None]
    for thread in video_threads + ptz_threads:
        thread.start()
    print(f"MaiaVision Edge: {len(video_threads)} cámara(s), {len(ptz_threads)} PTZ. Ctrl+C para detener.")
    try:
        while any(thread.is_alive() for thread in video_threads):
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for thread in video_threads + ptz_threads:
            thread.join(timeout=6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
