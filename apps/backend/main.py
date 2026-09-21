"""Private API and low-FPS authenticated MJPEG relay; no footage is stored."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from apps.backend.insights import InsightsStore

CAMERA_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
EVENTS = {"appearance", "disappearance", "motion_start", "motion_stop"}
STATUSES = {"NO DETECTADA", "SIN REFERENCIA", "QUIETA", "MOVIMIENTO", "SIN ANALISIS"}
MAX_JPEG_BYTES = 500_000
COOKIE = "maia_session"


@dataclass
class Settings:
    username: str
    password_hash: str
    session_secret: str
    edge_token: str
    cameras: dict[str, str]
    database: str = "data/maia.db"
    public_origin: str = "http://localhost:8080"
    secure_cookie: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            cameras = json.loads(os.getenv("MAIA_CAMERAS_JSON", '{"webcam":"Webcam Mac","android":"Android","cam3":"Cámara 3"}'))
        except json.JSONDecodeError as exc:
            raise RuntimeError("MAIA_CAMERAS_JSON no es JSON válido") from exc
        return cls(
            username=os.getenv("MAIA_ADMIN_USER", "admin"),
            password_hash=os.getenv("MAIA_ADMIN_PASSWORD_HASH", ""),
            session_secret=os.getenv("MAIA_SESSION_SECRET", ""),
            edge_token=os.getenv("MAIA_EDGE_TOKEN", ""),
            cameras=cameras,
            database=os.getenv("MAIA_DATABASE", "data/maia.db"),
            public_origin=os.getenv("MAIA_PUBLIC_ORIGIN", "http://localhost:8080").rstrip("/"),
            secure_cookie=os.getenv("MAIA_COOKIE_SECURE", "true").lower() == "true",
        )

    def validate(self) -> None:
        if not self.username or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", self.username):
            raise RuntimeError("MAIA_ADMIN_USER inválido")
        if not valid_password_hash(self.password_hash):
            raise RuntimeError("Configura MAIA_ADMIN_PASSWORD_HASH con scripts/hash_password.py")
        if len(self.session_secret) < 32 or len(self.edge_token) < 32:
            raise RuntimeError("MAIA_SESSION_SECRET y MAIA_EDGE_TOKEN requieren al menos 32 caracteres")
        if not isinstance(self.cameras, dict) or not self.cameras or len(self.cameras) > 12:
            raise RuntimeError("Configura entre 1 y 12 cámaras")
        if any(not isinstance(k, str) or not CAMERA_ID.fullmatch(k) or not isinstance(v, str) or not v.strip() or len(v) > 80 for k, v in self.cameras.items()):
            raise RuntimeError("MAIA_CAMERAS_JSON: IDs y nombres inválidos")
        if not self.public_origin.startswith(("https://", "http://localhost:", "http://127.0.0.1:")):
            raise RuntimeError("MAIA_PUBLIC_ORIGIN debe usar HTTPS fuera de localhost")
        if not self.secure_cookie and not self.public_origin.startswith(("http://localhost:", "http://127.0.0.1:")):
            raise RuntimeError("Cookies sin Secure solo se permiten en localhost")


def valid_password_hash(value: str) -> bool:
    try:
        method, rounds, salt, digest = value.split("$")
        return method == "pbkdf2_sha256" and 300_000 <= int(rounds) <= 2_000_000 and len(bytes.fromhex(salt)) >= 16 and len(bytes.fromhex(digest)) == 32
    except (ValueError, AttributeError):
        return False


def verify_password(password: str, stored: str) -> bool:
    if not valid_password_hash(stored):
        return False
    _, rounds, salt, expected = stored.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(actual, bytes.fromhex(expected))


def sign_session(settings: Settings) -> str:
    payload = f"{settings.username}:{int(time.time()) + 86400}:{secrets.token_hex(12)}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signature = hmac.new(settings.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def check_session(settings: Settings, token: str | None) -> bool:
    if not token or len(token) > 512:
        return False
    try:
        encoded, provided = token.split(".", 1)
        expected = hmac.new(settings.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, provided):
            return False
        value = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        username, expiry, _ = value.split(":", 2)
        return username == settings.username and int(expiry) >= time.time()
    except (ValueError, UnicodeDecodeError):
        return False


@dataclass
class CameraFrame:
    name: str
    jpeg: bytes | None = None
    status: str = "SIN ANALISIS"
    seen_at: str | None = None
    seen_mono: float = 0
    version: int = 0
    condition: threading.Condition = field(default_factory=threading.Condition)


class EventStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = threading.Lock()

    def init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, camera_id TEXT NOT NULL, event TEXT NOT NULL, status TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp DESC)")

    def append(self, timestamp: str, camera_id: str, event: str, status: str) -> None:
        with self.lock, sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO events(timestamp,camera_id,event,status) VALUES (?,?,?,?)", (timestamp, camera_id, event, status))
            connection.execute("DELETE FROM events WHERE datetime(timestamp) < datetime('now', '-7 days')")

    def recent(self, camera_id: str | None, limit: int) -> list[dict]:
        query = "SELECT id,timestamp,camera_id,event,status FROM events"
        params: list = []
        if camera_id:
            query += " WHERE camera_id = ?"
            params.append(camera_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params)]


class Login(BaseModel):
    username: str
    password: str


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    app = FastAPI(title="MaiaVision API", docs_url=None, redoc_url=None, openapi_url=None)
    cameras = {camera_id: CameraFrame(name=name) for camera_id, name in config.cameras.items()}
    store = EventStore(config.database)
    insights = InsightsStore(config.database)
    failures: dict[str, list[float]] = {}
    login_lock = threading.Lock()

    @app.on_event("startup")
    def startup() -> None:
        config.validate()
        store.init()
        insights.init()

    def require_user(request: Request) -> None:
        if not check_session(config, request.cookies.get(COOKIE)):
            raise HTTPException(status_code=401, detail="Inicia sesión")

    def require_edge(request: Request) -> None:
        expected = "Bearer " + config.edge_token
        provided = request.headers.get("authorization", "")
        if len(provided) > 512 or not hmac.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="Agente no autorizado")

    def origin_guard(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin != config.public_origin:
            raise HTTPException(status_code=403, detail="Origen no autorizado")

    def known_camera(camera_id: str) -> CameraFrame:
        if camera_id not in cameras:
            raise HTTPException(status_code=404, detail="Cámara desconocida")
        return cameras[camera_id]

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/login")
    def login(body: Login, request: Request) -> Response:
        origin_guard(request)
        peer = request.client.host if request.client else "unknown"
        with login_lock:
            failures[peer] = [v for v in failures.get(peer, []) if time.monotonic() - v < 900]
            if len(failures[peer]) >= 8:
                raise HTTPException(status_code=429, detail="Demasiados intentos. Prueba en 15 minutos")
        if not (hmac.compare_digest(body.username, config.username) and verify_password(body.password, config.password_hash)):
            with login_lock:
                failures.setdefault(peer, []).append(time.monotonic())
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        with login_lock:
            failures.pop(peer, None)
        response = JSONResponse({"username": config.username})
        response.set_cookie(COOKIE, sign_session(config), max_age=86400, httponly=True, secure=config.secure_cookie, samesite="strict", path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/logout")
    def logout(request: Request) -> Response:
        origin_guard(request)
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/", secure=config.secure_cookie, httponly=True, samesite="strict")
        return response

    @app.get("/api/me")
    def me(request: Request) -> dict:
        require_user(request)
        return {"username": config.username}

    @app.get("/api/cameras")
    def list_cameras(request: Request) -> list[dict]:
        require_user(request)
        result = []
        for camera_id, state in cameras.items():
            with state.condition:
                result.append({"id": camera_id, "name": state.name, "status": state.status,
                               "online": state.jpeg is not None and time.monotonic() - state.seen_mono < 20,
                               "seen_at": state.seen_at})
        return result

    @app.get("/api/cameras/{camera_id}/snapshot")
    def snapshot(camera_id: str, request: Request) -> Response:
        require_user(request)
        state = known_camera(camera_id)
        with state.condition:
            jpeg = state.jpeg if time.monotonic() - state.seen_mono < 20 else None
        if jpeg is None:
            raise HTTPException(status_code=404, detail="Cámara sin señal reciente")
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/cameras/{camera_id}/stream")
    def stream(camera_id: str, request: Request) -> StreamingResponse:
        require_user(request)
        state = known_camera(camera_id)

        def frames() -> Iterator[bytes]:
            last = -1
            while True:
                with state.condition:
                    state.condition.wait_for(lambda: state.version != last, timeout=12)
                    if state.version == last:
                        payload = b"--frame\r\nContent-Type: text/plain\r\n\r\nwaiting\r\n"
                    else:
                        last = state.version
                        jpeg = state.jpeg if time.monotonic() - state.seen_mono < 20 else None
                        payload = (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n") if jpeg else b""
                if payload:
                    yield payload  # Never hold the condition lock during network backpressure.

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/api/events")
    def events(request: Request, camera_id: str | None = None, limit: int = 50) -> list[dict]:
        require_user(request)
        if camera_id is not None:
            known_camera(camera_id)
        if not 1 <= limit <= 200:
            raise HTTPException(status_code=422, detail="limit debe estar entre 1 y 200")
        return store.recent(camera_id, limit)

    @app.get("/api/insights")
    def get_insights(request: Request, window_minutes: int = 60) -> dict:
        require_user(request)
        if not 15 <= window_minutes <= 1440:
            raise HTTPException(status_code=422, detail="window_minutes debe estar entre 15 y 1440")
        return insights.summary(config.cameras, window_minutes)

    @app.post("/api/edge/{camera_id}/frame")
    async def receive_frame(camera_id: str, request: Request) -> dict:
        require_edge(request)
        state = known_camera(camera_id)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "image/jpeg":
            raise HTTPException(status_code=415, detail="Se requiere image/jpeg")
        if int(request.headers.get("content-length", "0") or 0) > MAX_JPEG_BYTES:
            raise HTTPException(status_code=413, detail="Imagen demasiado grande")
        payload = await request.body()
        if len(payload) > MAX_JPEG_BYTES or len(payload) < 4:
            raise HTTPException(status_code=413, detail="JPEG vacío o demasiado grande")
        if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
            raise HTTPException(status_code=422, detail="JPEG inválido")
        status = request.headers.get("x-maia-status", "SIN ANALISIS")
        event = request.headers.get("x-maia-event", "")
        if status not in STATUSES or (event and event not in EVENTS):
            raise HTTPException(status_code=422, detail="Estado o evento inválido")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with state.condition:
            state.jpeg = payload
            state.status = status
            state.seen_at = timestamp
            state.seen_mono = time.monotonic()
            state.version += 1
            state.condition.notify_all()
        if event:
            store.append(timestamp, camera_id, event, status)
        insights.record(camera_id, status)
        return {"ok": True}

    return app


app = create_app()
