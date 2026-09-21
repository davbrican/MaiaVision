# 🐾 MaiaVision — monitor privado de mascotas

Monorepo de tres aplicaciones: agente Python/OpenCV/YOLO (Mac o Raspberry), API FastAPI/SQLite y dashboard responsive React. Fuentes: webcam, Android MJPEG/RTSP, cámaras IP y vídeos de prueba. La versión actual entrega JPEG/MJPEG a pocos FPS; **no** dispone aún de WebRTC/HD, grabación, alertas, audio ni identificación individual de Maia.

**Estado:** funcionalidad integrada en la rama `feat/web-dashboard-multicamera-android` / [PR #1](https://github.com/davbrican/MaiaVision/pull/1). Los tests de Python/API y la compilación frontend pasan en CI; **no se ha desplegado ni probado con hardware real ni en el VPS**. `main` todavía contiene la versión anterior hasta que se revise y fusione la PR.

## Arquitectura

```text
Mac / Raspberry
  ├── webcam integrada / Android MJPEG / cámaras RTSP
  └── apps/edge/agent.py: OpenCV + YOLO opcional, JPEG reducido 1–5 FPS
          └── HTTPS + MAIA_EDGE_TOKEN → maiavision.dbrincau.com/api/edge/{id}/frame
                   └── Nginx del host (HTTPS 443) → 127.0.0.1:8102 (Docker frontend)
                          ├── React/Nginx: dashboard privado y MJPEG
                          └── FastAPI/SQLite: sesiones, eventos (7 días), último frame en RAM
                                    ↑
                              navegador móvil
```

Sólo el agente de casa accede a las IP privadas de las cámaras. El VPS **no necesita puertos abiertos del router doméstico**. La cámara Android puede emitir localmente por su propio puerto `8080`; ese puerto no tiene relación con el **8102 del VPS**. Los JPEG sí salen de casa hacia el VPS por HTTPS, aunque no haya espectadores.

## 1. Obtener la versión multicámara

```bash
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
```

Requisitos: Python 3.11+, Docker y Compose para el servidor, webcam y permisos locales. Para compilar React fuera de Docker: Node 22.

## 2. VPS: Docker + Nginx existente

Antes de desplegar, comprueba que `8102` esté libre tanto en contenedores como en el sistema:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
sudo ss -ltnp | grep ':8102 '
```

Prepara secretos **dentro del VPS** (nunca los subas a Git):

```bash
cp .env.example .env
python3 scripts/hash_password.py
python3 -c 'import secrets; print(secrets.token_hex(32))'  # Ejecutar DOS veces; valores distintos
```

Sustituye todas las líneas `CHANGEME` en `.env` y configura:

```dotenv
MAIA_PUBLIC_ORIGIN=https://maiavision.dbrincau.com
MAIA_COOKIE_SECURE=true
MAIA_CAMERAS_JSON='{"webcam":"Webcam MacBook","android":"Android WiFi","cam3":"Pasillo"}'
```

Usa el hash completo que imprime el script, una clave de sesión distinta del token del edge y ejecuta `chmod 600 .env`. Después:

```bash
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://127.0.0.1:8102/api/health
```

**Puertos:** frontend `127.0.0.1:8102:80` exclusivamente; backend `8000` únicamente dentro de Docker. En `/etc/nginx/sites-available/maiavision.dbrincau.com` configura el HTTPS público para que el `location /` haga `proxy_pass http://127.0.0.1:8102;`. Para MJPEG, usa `proxy_buffering off;` y un timeout de lectura apropiado. Reutiliza el Nginx existente y no modifiques los virtual hosts de otros proyectos. Revisa [guía de despliegue y configuración Nginx](docs/deployment.md) antes de activar el dominio. No expongas 8102 al exterior.

## 3. Mac: webcam apuntando al VPS

El agente se ejecuta **nativamente**, no dentro de Docker, para acceder a la cámara del ordenador. Reutiliza el mismo repo/rama en el Mac y crea su entorno:

```bash
python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install -r apps/edge/requirements.txt
export MAIA_EDGE_TOKEN='EL_TOKEN_PRIVADO_DEL_VPS'
python -m apps.edge.agent --config config/cameras.mac.json --backend https://maiavision.dbrincau.com --fps 2 --no-vision
```

`--no-vision` verifica vídeo y comunicaciones sin YOLO. Elimínalo para activar detección (la primera vez descarga pesos). Si el Mac usa el backend del VPS, **no** pongas `localhost:8102` en `--backend`: usaría el propio Mac. Accede al dashboard del teléfono desde `https://maiavision.dbrincau.com`.

## 4. Android como segunda cámara

Instala una aplicación de cámara IP con MJPEG HTTP/RTSP, por ejemplo [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam). Conecta Android y Mac a la misma WiFi, inicia servidor, comprueba la URL real del flujo (la portada HTML no es el vídeo) y exporta:

```bash
export MAIA_ANDROID_URL='http://IP_LOCAL_ANDROID:PUERTO/RUTA_DE_VIDEO'
python -m apps.edge.agent --config config/cameras.android.example.json --backend https://maiavision.dbrincau.com --fps 2 --no-vision
```

El agente abre **webcam + Android**. `MAIA_EDGE_TOKEN` debe estar exportado. No abras puertos de cámaras en el router. [Instrucciones detalladas](docs/android.md).

## 5. Desarrollo completamente local (opcional)

Si el servidor Docker corre en el propio Mac, en el `.env` LOCAL usa `MAIA_PUBLIC_ORIGIN=http://localhost:8102` y `MAIA_COOKIE_SECURE=false` (no usar esto en VPS), inicia Compose, visita `http://localhost:8102` y ejecuta `--backend http://localhost:8102`. El puerto de la aplicación Android es independiente.

## 6. Raspberry y tres cámaras (futuro)

Instala Edge en la Pi ARM64, define `MAIA_EDGE_TOKEN` y URLs RTSP/MJPEG en un `edge.env` protegido, utiliza `config/cameras.raspberry.example.json` y el mismo dominio HTTPS. Prueba primero `--fps 1 --width 480 --no-vision`; activa YOLO gradualmente después de medir CPU, memoria y temperatura. [Guía de migración](docs/deployment.md). No afirmar rendimiento de tres detectores sin medir.

## Componentes y API

| Ruta | Contenido |
|---|---|
| `apps/edge/agent.py` | Captura multi-fuente, reconexión, tracker por cámara, inferencia YOLO opcional y envío HTTPS. |
| `apps/backend/main.py` | Login, sesiones, JPEG/MJPEG autenticado, lista de cámaras, eventos SQLite. |
| `apps/frontend/` | React/TS, login, selector/mosaico, reproducción y eventos. |
| `infra/docker-compose.yml` | Backend y frontend; proxy frontend ligado sólo a `127.0.0.1:8102`. |
| `config/` | Ejemplos Mac, Android, Pi; URLs reales mediante variables entorno. |
| `AGENTS.md` | Estándares de implementación, privacidad y criterios de aceptación. |

Rutas API: `POST /api/login`, `/api/logout`, `GET /api/me`, `/api/cameras`, `/api/cameras/{id}/snapshot`, `/api/cameras/{id}/stream`, `/api/events` (sesión), `POST /api/edge/{id}/frame` (token edge), `GET /api/health`. Los JPEG sólo permanecen temporalmente en RAM; eventos de texto en SQLite durante siete días. Un solo worker de backend por su relay en memoria.

## Tests

```bash
python -m pip install -r apps/backend/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py maia_vision apps tests scripts
cd apps/frontend && npm install && npm run build
```

CI no sustituye pruebas de cámaras físicas, TLS, Safari y despliegue. Sigue pendiente MediaMTX/WebRTC, alertas, audio, zonas, grabaciones, PWA y multiusuario/MFA. No atribuir sueño, ansiedad ni identidad de Maia a un detector genérico: `QUIETA` sólo indica un desplazamiento aparente pequeño y `NO DETECTADA` significa que el detector no la ve. Revisa licencias de Ultralytics antes de redistribuir/comercializar el producto. No hay licencia propia del proyecto definida.
