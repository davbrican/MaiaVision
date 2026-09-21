# 🐾 MaiaVision — monitor privado de mascotas

Monorepo de **tres aplicaciones**: agente de cámaras Python/OpenCV/YOLO para Mac o Raspberry Pi, API privada FastAPI/SQLite y dashboard responsive React. Admite webcam integrada, móvil Android como cámara MJPEG/RTSP, cámaras WiFi RTSP/MJPEG y vídeos de prueba. De momento el servidor retransmite vistas **MJPEG/JPEG a pocos FPS** (no HD/WebRTC) con sesiones autenticadas. No almacena vídeo, audio ni imágenes: solo eventos textuales durante siete días. Compatible con una, dos o tres cámaras a la vez, siempre que los ID coincidan en ambas configuraciones.

**Estado:** versión integrada implementada en rama de feature; pruebas CI automatizadas para lógica, API y compilación web. Las pruebas reales con móviles, Raspberry, hardware, DNS y VPS requieren dispositivos y credenciales que no están disponibles en GitHub. **No se ha desplegado en tu VPS ni se puede afirmar que tres flujos/YOLO rindan adecuadamente en Raspberry sin benchmark.**

## Arquitectura

```text
[Mac / Raspberry] webcam 0 + Android MJPEG + WiFi RTSP
   apps/edge/agent.py → OpenCV + YOLO opcional → JPEG reducido (1-5 FPS por fuente)
       └─ HTTPS + token exclusivo EDGE → VPS /api/edge/{id}/frame
                                             ┌─ FastAPI: sesiones, eventos SQLite (7 días)
                                             └─ retransmisión MJPEG en RAM (sin grabar)
                                                    ↑ sesiones privadas HttpOnly
                                              Nginx + React responsive
                                                    ↑ HTTPS público (Caddy/proxy existente)
                                              navegador del iPhone
```

La captura y el análisis ocurren en el ordenador o Raspberry. El servidor NO se conecta a las IP privadas de las cámaras: el agente realiza conexiones **salientes** al backend, por lo que no es necesario abrir puertos del router. Se envían imágenes reducidas por HTTPS (al verlas se procesan en el VPS). Para una instalación definitiva de alta calidad se propone MediaMTX + WebRTC/HLS y red privada, **todavía no implementados**. Esta primera versión es un monitor de baja frecuencia, no un NVR profesional ni un sistema de alarma.

## 1. Arranque rápido sin cámaras adicionales

Requisitos: Python 3.11+, Docker + Docker Compose, una webcam, Node 22 solo si desarrollas el frontend fuera de Docker. Docker ejecuta servidor/API/frontend; el agente se ejecuta **nativamente** en el Mac para acceder a la webcam.

```bash
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
cp .env.example .env
python3 scripts/hash_password.py     # Copia su línea COMPLETA en .env
python3 -c 'import secrets; print(secrets.token_hex(32))'  # Genera 2 valores DIFERENTES para SESSION_SECRET y EDGE_TOKEN
# Edita .env con esos valores; NO comitas .env.
docker compose -f infra/docker-compose.yml up -d --build
# Comprueba http://localhost:8080/api/health
```

Abre **http://localhost:8080** y entra con el usuario y contraseña que configuraste. Se mostrará el dashboard, pero la webcam todavía aparecerá desconectada hasta que arranques el agente:

```bash
python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install -r apps/edge/requirements.txt
set -a; source .env; set +a
python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8080 --no-vision
```

`--no-vision` es el modo vídeo para comprobar webcam, conexión y login sin descargar YOLO. Retíralo para la detección real; la primera ejecución descargará los pesos `yolo26n.pt`. Controla CPU/RAM y baja a `--fps 1` o `--width 480` si va lento. Detén el agente con `Ctrl+C`.

Para abrir la web desde el teléfono en la misma WiFi **en desarrollo**, el servicio está ligado solo a localhost por seguridad: configura primero un proxy HTTPS privado o sigue `docs/deployment.md`; no publiques `8080` sin protección TLS. En la instalación VPS real accederás desde el dominio HTTPS, desde cualquier red.

## 2. Añadir Android como segunda cámara

Consulta [docs/android.md](docs/android.md) para instrucciones de la aplicación IP Webcam, comprobación de la URL real y medidas de seguridad. Tras iniciar su servidor de vídeo en la misma WiFi que el Mac:

```bash
export MAIA_ANDROID_URL='http://192.168.1.50:8080/video'  # Sustituir por IP/puerto/ruta REALES
python -m apps.edge.agent --config config/cameras.android.example.json --backend http://localhost:8080 --no-vision
```

El mismo agente abrirá la webcam y el Android simultáneamente. El ID `android` ya figura en `.env.example`; una tercera cámara puede usar `cam3` en `config/cameras.raspberry.example.json`. Variables con contraseñas de cámaras deben ir en `edge.env` (ignorado por Git) y nunca en los JSON versionados. Mantén desactivadas las opciones de nube de la aplicación Android si quieres todo el vídeo restringido a tu infraestructura.

## 3. Raspberry + tres cámaras + VPS

Consulta [docs/deployment.md](docs/deployment.md). En el VPS prepara un dominio, DNS, HTTPS y `.env` de producción (`MAIA_PUBLIC_ORIGIN=https://tu-dominio`, `MAIA_COOKIE_SECURE=true`). `docker compose -f infra/docker-compose.yml up -d --build` escucha SOLO en `127.0.0.1:8080`: configura Caddy/Nginx del host como proxy TLS. En la Raspberry configura `edge.env` con únicamente el token y las URL de las cámaras, instala las dependencias ARM compatibles y ejecuta el agente con `--config config/cameras.raspberry.example.json --backend https://tu-dominio`. No abras RTSP de cámaras a Internet.

## Servicios y código

| Ruta | Responsabilidad |
| --- | --- |
| `apps/edge/agent.py` | Varias fuentes OpenCV, un detector YOLO compartido, rastreador por cámara, reconexión y envío HTTPS. |
| `apps/backend/main.py` | Login, cookies firmadas, lista de cámaras, JPEG/MJPEG autenticado, recepción con token y eventos SQLite. |
| `apps/frontend/` | React + TS + Vite, login responsive, selector, mosaico, reproducción y eventos. |
| `infra/docker-compose.yml` | API + frontend Nginx. Datos SQLite persistidos en `data/`. |
| `config/` | Fuentes de ejemplo Mac, Android y Raspberry. URLs privadas mediante variables de entorno. |
| `scripts/hash_password.py` | Hash PBKDF2 con sal de contraseña de acceso. |
| `main.py` | Monitor OpenCV legado, solo local; se conserva por compatibilidad. |
| `AGENTS.md` | Contrato técnico para agentes, seguridad, arquitectura y criterios de aceptación. |

## API mínima

- `POST /api/login`, `POST /api/logout`, `GET /api/me`: cookie HttpOnly SameSite Strict; mutaciones web exigen origen exacto.
- `GET /api/cameras`, `/api/cameras/{id}/snapshot`, `/api/cameras/{id}/stream`, `GET /api/events`: sesión obligatoria.
- `POST /api/edge/{id}/frame`: `Authorization: Bearer <MAIA_EDGE_TOKEN>`, `Content-Type: image/jpeg`, máximo 500 kB, ID permitido.
- `GET /api/health`: únicamente estado básico. No se publican tokens ni URL privadas en API o frontend.

Los JPEG están temporalmente **en memoria** y no se guardan en disco; los eventos sí se guardan en SQLite durante siete días. Si el backend reinicia, las vistas desaparecen hasta recibir nuevos fotogramas. Esta versión usa un proceso Uvicorn, ya que los fotogramas están en memoria local del proceso. No escales a múltiples workers sin mover el relay a un media server/broker.

## Pruebas

```bash
python -m pip install -r apps/backend/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py maia_vision apps tests scripts
cd apps/frontend && npm install && npm run build
```

GitHub Actions ejecuta sintaxis, tests sin cámara y compilación React. Solo una prueba con dispositivos reales puede validar calidad, FPS, temperatura, red, reconexión y reproducción en Safari iOS.

## Seguridad, limitaciones y siguientes fases

- `.env` y `edge.env` NO se suben. Cambia todos los secretos y utiliza HTTPS real antes de abrir el dominio público. Las credenciales de Android/RTSP permanecen en la Raspberry/Mac.
- El administrador es **un único usuario**, con inicio de sesión y 8 intentos fallidos por IP/15 minutos por proceso; sin MFA ni gestión multiusuario. Los tokens de edge son compartidos por los agentes y deben rotarse si se filtran. Evita accesos ajenos al área vigilada.
- Este MVP envía imágenes al VPS aunque no haya espectadores; configura FPS bajo, estima ancho de banda y respeta privacidad de personas que puedan salir en cámara. Sin audio, grabaciones, zonas, alertas, notificaciones ni identificación individual de Maia.
- `QUIETA` solo expresa desplazamiento pequeño del centro de una caja; `NO DETECTADA` no confirma que el animal esté fuera de la habitación ni permite diagnosticar ansiedad o sueño.
- Futuro: autenticación individual por agente, retención configurable, heartbeats, streaming adaptativo MediaMTX/WebRTC, desacoplar inferencia en Raspberry, PWA, zonas, alertas y análisis de ladridos opt-in (micrófono + clasificador aparte).

No se ha elegido una licencia del código propio. Si se redistribuye/comercializa la integración con Ultralytics, revisar su licencia AGPL-3.0/Enterprise y dependencias.
