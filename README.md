# 🐾 MaiaVision — monitor privado de mascotas

Monorepo de tres aplicaciones: agente Python/OpenCV/YOLO (Mac, Linux o Raspberry), API FastAPI/SQLite y dashboard responsive React. Fuentes: webcam, Android MJPEG/RTSP, cámaras IP y vídeos de prueba. La versión actual entrega JPEG/MJPEG a pocos FPS; **no** dispone aún de WebRTC/HD, grabación, alertas, audio ni identificación individual de Maia.

**Estado:** desarrollo en `feat/web-dashboard-multicamera-android` / [PR #1](https://github.com/davbrican/MaiaVision/pull/1); `main` sigue conteniendo la versión anterior hasta la revisión y fusión. El usuario ha confirmado que su VPS, la webcam del Mac y el Android funcionan con la primera versión. Las evoluciones posteriores, otros ordenadores y nuevas cámaras requieren despliegue y prueba específica; CI no verifica dispositivos físicos.

## Arquitectura

```text
Ordenador de casa / Raspberry (agente Edge)
  ├── webcam / Android MJPEG / cámaras IP RTSP o MJPEG
  └── apps/edge/agent.py: OpenCV + YOLO opcional, JPEG reducido 1–5 FPS
          └── HTTPS + MAIA_EDGE_TOKEN → maiavision.dbrincau.com/api/edge/{id}/frame
                   └── Nginx del host (HTTPS 443) → 127.0.0.1:8102 (Docker frontend)
                          ├── React/Nginx: dashboard privado y MJPEG
                          └── FastAPI/SQLite: sesiones, eventos e indicadores, último frame en RAM
                                    ↑
                              navegador móvil
```

Solo el agente de casa accede a las IP privadas de las cámaras. El VPS **no necesita puertos abiertos del router doméstico**. La cámara Android puede emitir localmente por su propio puerto `8080`; ese puerto no tiene relación con el **8102 del VPS**. Los JPEG sí salen de casa hacia el VPS por HTTPS, aunque no haya espectadores.

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

Prepara secretos **dentro del VPS** solo en la instalación inicial (nunca los subas a Git):

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

Usa el hash completo que imprime el script, una clave de sesión distinta del token del edge y ejecuta `chmod 600 .env`. **En una instalación existente no recrees `.env` ni regeneres secretos para añadir cámaras o cambiar de ordenador.** Después:

```bash
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://127.0.0.1:8102/api/health
```

**Puertos:** frontend `127.0.0.1:8102:80` exclusivamente; backend `8000` únicamente dentro de Docker. El archivo Nginx utilizado en este VPS es `/etc/nginx/sites-available/maiavision`, con su enlace en `sites-enabled`; `server_name maiavision.dbrincau.com` y `proxy_pass http://127.0.0.1:8102;`. Para MJPEG, usa `proxy_buffering off;` y un timeout de lectura apropiado. Reutiliza el Nginx existente y no modifiques los virtual hosts de otros proyectos. Revisa [guía de despliegue](docs/deployment.md). No expongas 8102 al exterior.

## 3. Mac: webcam apuntando al VPS

El agente se ejecuta **nativamente**, no dentro de Docker, para acceder a la cámara del ordenador. Reutiliza el mismo repo/rama en el Mac y crea su entorno:

```bash
python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install -r apps/edge/requirements.txt
export MAIA_EDGE_TOKEN='EL_TOKEN_PRIVADO_DEL_VPS'
python -m apps.edge.agent --config config/cameras.mac.json --backend https://maiavision.dbrincau.com --fps 2 --no-vision
```

`--no-vision` verifica vídeo y comunicaciones sin YOLO. Elimínalo para activar detección (la primera vez puede descargar pesos). Si el Mac usa el backend del VPS, **no** pongas `localhost:8102` en `--backend`: usaría el propio Mac. Accede al dashboard desde `https://maiavision.dbrincau.com`.

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

## 7. Manual de mantenimiento: nuevas cámaras y sustitución del ordenador

**Qué se configura y dónde:**

| Dónde | Archivo | Función |
| --- | --- | --- |
| **VPS** `~/MaiaVision` | `.env` → `MAIA_CAMERAS_JSON` | Registro de los **ID permitidos** y nombres mostrados en el dashboard. No contiene URL de las cámaras. |
| **Ordenador de casa / Pi** | `edge.env` | Token compartido con el VPS, URL pública HTTPS del backend y URL **privadas** de cámaras. |
| **Ordenador de casa / Pi** | `config/cameras.local.json` | Lista real de fuentes que abre ese agente, una entrada por cámara. Este nombre está excluido por `.gitignore`. |
| **VPS** | Docker Compose + Nginx | Se mantiene en `127.0.0.1:8102` y `https://maiavision.dbrincau.com`; **no** cambia al añadir cámaras o sustituir el Mac. |

Los identificadores deben coincidir **exactamente** entre `MAIA_CAMERAS_JSON` del VPS y `id` de la configuración del agente. Son únicos, de 1–32 caracteres (`a-z`, `0-9`, `_`, `-`); el backend admite de 1 a 12 cámaras. No reutilices el mismo ID para dos cámaras diferentes que funcionen a la vez. El campo `name` del JSON local es una etiqueta para el agente; el nombre visible del dashboard lo define el VPS. Cambiar un ID genera una fuente diferente y rompe la continuidad de su historial; para sustituir físicamente una cámara conservando su ubicación, puedes mantener su ID.

### 7.1. Añadir una cámara IP RTSP o MJPEG (paso a paso)

**1 — Cámara y red doméstica.** Conecta la cámara IP y el ordenador que ejecuta Edge a la misma LAN o a una VPN privada con acceso a esa LAN. Configura contraseña fuerte y, preferiblemente, reserva DHCP. Activa RTSP o MJPEG solo si lo admite el fabricante, y obtén la **ruta real** de su manual/interfaz. Comprueba el vídeo desde el ordenador Edge mediante VLC o un navegador si es HTTP. Las siguientes URL son solo plantillas, **no rutas universales**:

```text
rtsp://USUARIO:CONTRASENA@IP_PRIVADA:554/RUTA_REAL
http://IP_PRIVADA:PUERTO/RUTA_MJPEG_REAL
```

No abras puertos RTSP/HTTP de la cámara en el router ni envíes URLs con credenciales por chat o a Git. Si la cámara usa credenciales especiales en la URL, codifícalas correctamente según el fabricante.

**2 — VPS: dar de alta el ID.** Edita el `.env` ya existente:

```bash
# SOLO VPS
cd ~/MaiaVision
nano .env
```

Edita **solo** `MAIA_CAMERAS_JSON`, conservando los ID que sigas utilizando. Ejemplo con la cámara nueva `cam4`:

```dotenv
MAIA_CAMERAS_JSON='{"webcam":"Webcam","android":"Android dormitorio","cam3":"Pasillo","cam4":"Cámara terraza"}'
```

No pongas la URL RTSP aquí, no hagas `cp .env.example .env` ni alteres `MAIA_EDGE_TOKEN`, `MAIA_SESSION_SECRET` o el hash de contraseña. Aplica la lista al backend y comprueba su salud:

```bash
# SOLO VPS
docker compose -f infra/docker-compose.yml up -d --no-deps --force-recreate backend
docker compose -f infra/docker-compose.yml ps
curl -fsS http://127.0.0.1:8102/api/health
```

El reinicio del backend interrumpe brevemente las vistas en RAM; no borra la base SQLite. La cámara nueva aparecerá sin señal hasta que el agente envíe fotogramas.

**3 — Ordenador Edge: URL y fuente.** En el equipo que llega a la IP privada de la cámara, añade a `edge.env` una variable distinta por cámara:

```dotenv
MAIA_CAM4_URL='rtsp://USUARIO:CONTRASENA@IP_PRIVADA:554/RUTA_REAL'
```

Para una cámara HTTP/MJPEG, la variable puede contener la URL `http://...` correspondiente y su `type` en el JSON será `mjpeg` (o `rtsp` para RTSP). Protege el archivo:

```bash
# SOLO ORDENADOR EDGE, desde la raíz del repo
chmod 600 edge.env
```

Crea `config/cameras.local.json` (no se sube a Git). **Incluye también las cámaras que deseas conservar**; el agente sustituye toda su lista al arrancar. Ejemplo de webcam, Android existente y cámara IP RTSP nueva:

```json
{
  "cameras": [
    {"id": "webcam", "name": "Webcam", "type": "webcam", "device": 0},
    {"id": "android", "name": "Android", "type": "android", "source_env": "MAIA_ANDROID_URL"},
    {"id": "cam4", "name": "Terraza", "type": "rtsp", "source_env": "MAIA_CAM4_URL"}
  ]
}
```

Si no hay webcam, **quita su entrada**. Si la IP emite MJPEG, cambia `"type": "rtsp"` por `"type": "mjpeg"`. Nunca escribas URL o contraseña directamente en el JSON; usa `source_env`.

**4 — Probar y activar.** Detén con `Ctrl+C` el agente anterior si es un proceso manual. En el ordenador Edge:

```bash
cd ~/MaiaVision
source .venv-edge/bin/activate
set -a; source ./edge.env; set +a
python -m apps.edge.agent --config config/cameras.local.json --backend https://maiavision.dbrincau.com --fps 1 --width 480 --no-vision
```

Comprueba en el dashboard que **todas** las fuentes deseadas estén en línea. Para activar detección, detén con `Ctrl+C` y ejecuta lo mismo sin `--no-vision`. Empieza con 1 FPS por cámara y verifica CPU, RAM, temperatura y red; varias cámaras incrementan el trabajo y el ancho de banda. Si usas un servicio `systemd`, **no ejecutes simultáneamente el agente manual**: detén primero `sudo systemctl stop maia-edge`, actualiza `ExecStart` para apuntar a `config/cameras.local.json`, y después `sudo systemctl daemon-reload && sudo systemctl start maia-edge`.

### 7.2. Añadir un segundo, tercer... Android

En **cada móvil**, instala e inicia una aplicación de cámara WiFi compatible (por ejemplo IP Webcam), conéctalo a la misma red doméstica del Edge y comprueba desde ese ordenador la URL directa del vídeo. Cada móvil tiene su **propia IP**; pueden utilizar el mismo puerto local `8080` sin conflicto. Evita suspensión de la aplicación y sobrecalentamiento; no expongas las URL a Internet.

Repite los pasos de la sección 7.1 con **un ID y una variable diferentes por Android**. Ejemplo de segundo móvil:

- En el `.env` del **VPS**, añade `"android2":"Android cocina"` a `MAIA_CAMERAS_JSON`, sin eliminar los ID previos, y recrea **solo** el servicio `backend` con el comando de la sección 7.1.
- En `edge.env` del **ordenador**, añade `MAIA_ANDROID2_URL='http://IP_REAL_ANDROID_2:PUERTO/RUTA_VIDEO_REAL'`.
- En `config/cameras.local.json`, añade al array, conservando las demás entradas:

```json
{"id": "android2", "name": "Android cocina", "type": "android", "source_env": "MAIA_ANDROID2_URL"}
```

Reinicia únicamente el agente que gestiona ese móvil y comprueba las dos fuentes `android` y `android2` en el mosaico. No uses el mismo `source_env` para móviles distintos ni reutilices el ID `android`. [Configuración detallada de IP Webcam](docs/android.md).

### 7.3. Sustituir el Mac por otro PC o Raspberry, sin cambiar el VPS

**Regla de migración:** quien ejecuta `apps.edge.agent` necesita acceso local a las cámaras y salida HTTPS al dominio, **no** acceso al Docker del VPS. Mantén los mismos ID para las fuentes que sustituyen a las antiguas, deja de lanzar el agente viejo antes del nuevo y conserva en el VPS `.env`, puerto `8102`, HTTPS y SQLite. Si no trasladas la webcam del Mac, puedes quitarla del JSON del Edge y, opcionalmente, de `MAIA_CAMERAS_JSON` del VPS; si se queda registrada, el dashboard la mostrará desconectada. No copies el `.env` completo del VPS al ordenador: contiene secretos de administración que Edge no necesita.

**Ordenador nuevo Ubuntu/Debian, comandos en orden** (usuario normal con `sudo`; **NO** ejecutar en el VPS):

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ca-certificates curl
python3 --version                 # Debe ser 3.11+
cd ~
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/edge/requirements.txt
```

Si la versión Python es inferior a 3.11, instala una compatible antes de seguir. En Raspberry/ARM, PyTorch/Ultralytics puede necesitar una instalación específica; valida vídeo con `--no-vision` y mide el rendimiento antes de activar YOLO.

Guarda **únicamente** datos del agente en el nuevo ordenador:

```bash
cd ~/MaiaVision
umask 077
nano edge.env
```

Ejemplo para mover el Android al ordenador nuevo (sustituye el token en privado por el valor **actual** del VPS, y la URL por la dirección real del móvil):

```dotenv
MAIA_EDGE_TOKEN='TOKEN_ACTUAL_DEL_VPS'
MAIA_BACKEND_URL='https://maiavision.dbrincau.com'
MAIA_ANDROID_URL='http://IP_REAL_ANDROID:PUERTO/RUTA_VIDEO_REAL'
```

Crea la lista del agente **sin webcam** si el equipo nuevo no tiene una. Este fichero `.local.json` está ignorado por Git:

```bash
cp config/cameras.android-only.example.json config/cameras.local.json
chmod 600 edge.env
set -a; source ./edge.env; set +a
curl -fsS https://maiavision.dbrincau.com/api/health
```

Si el equipo tiene webcam USB y quieres incluirla, utiliza `cp config/cameras.android.example.json config/cameras.local.json` en su lugar; si instalas cámaras IP, construye el JSON según la sección 7.1. Para webcam Linux, puede ser necesario revisar el índice `device` y permisos de `/dev/video*`.

**En el Mac antiguo:** para el agente manual, pulsa `Ctrl+C`; si funcionaba como servicio, detén dicho servicio. De esta forma dos agentes no envían simultáneamente fotogramas al mismo ID. **En el PC nuevo**, con el entorno cargado:

```bash
python -m apps.edge.agent --config config/cameras.local.json --backend https://maiavision.dbrincau.com --fps 1 --width 480 --no-vision
```

Cuando la cámara aparezca en el dashboard, pulsa `Ctrl+C` y vuelve a ejecutar el comando sin `--no-vision` para activar YOLO. Si no hay servidor de vídeo local accesible, el agente no podrá abrir una IP privada del Android por estar físicamente en otra red. Tampoco es necesario desplegar Docker en este ordenador: Docker permanece exclusivamente en el VPS.

**Arranque automático opcional (Ubuntu/Debian):** detén primero el proceso manual. Instala un servicio `systemd` con usuario no privilegiado, `WorkingDirectory` apuntando al repo, `EnvironmentFile` apuntando a `edge.env`, y `ExecStart` apuntando al Python de `.venv-edge` y a `config/cameras.local.json`. La guía [docs/new-edge-computer.md](docs/new-edge-computer.md#e-arranque-automático-con-systemd-ubuntudebian-opcional) contiene los comandos completos: sustituye allí la ruta `config/cameras.android-only.example.json` por `config/cameras.local.json` si has personalizado la lista. Para Windows/PowerShell y macOS hay instrucciones específicas en ese mismo documento; **no** uses comandos de `apt` o `systemd` en esos sistemas.

**Actualizar el agente de ese PC:** para ejecución manual, detén con `Ctrl+C`, luego `cd ~/MaiaVision && git pull --ff-only` y vuelve a lanzarlo desde el venv. Con `systemd`, ejecuta `sudo systemctl stop maia-edge`, actualiza la rama y luego `sudo systemctl start maia-edge`; verifica `sudo systemctl status maia-edge --no-pager`. Los ficheros privados `edge.env` y `config/cameras.local.json` no se sobrescriben con el pull.

### 7.4. Problemas frecuentes y seguridad

| Síntoma | Comprobación |
| --- | --- |
| Cámara nueva no aparece | Comprueba el ID tanto en `MAIA_CAMERAS_JSON` del VPS como en el JSON Edge; recrea backend después de editar `.env`. |
| Aparece, pero sin señal | Comprueba URL real del stream, WiFi/LAN, credenciales, permisos, IP/DHCP y logs del agente; nunca publiques credenciales. |
| Error HTTP 401 del agente | `MAIA_EDGE_TOKEN` debe coincidir exactamente con el del VPS; si se rota, actualiza **todos** los agentes. |
| Error HTTP 404 al subir frames | ID del JSON local no registrado en el backend. |
| Una cámara se intercambia con otra | No ejecutes dos agentes subiendo al mismo ID y no reutilices un `source_env` para fuentes distintas. |
| Veo vídeo, pero no actividad | El agente se lanzó con `--no-vision` o aún no hay detecciones; no inferir bienestar o ubicación exacta de las pérdidas de visión. |
| El servicio automático no refleja un cambio | Edita `ExecStart`/`edge.env`, `sudo systemctl daemon-reload` si cambió el fichero de servicio y `sudo systemctl restart maia-edge`. |

No pongas URL privadas en frontend ni VPS, no publiques RTSP/MJPEG, no añadas cámara o agente con secretos al repositorio, usa HTTPS para Edge→VPS y consulta a las personas que puedan aparecer en la imagen. Los agentes existentes comparten actualmente un token: si uno se compromete, rota el token en el VPS y en todos ellos. Las muestras e indicadores estiman observaciones, no identidad o estados emocionales.

## Componentes y API

| Ruta | Contenido |
|---|---|
| `apps/edge/agent.py` | Captura multi-fuente, reconexión, tracker por cámara, inferencia YOLO opcional y envío HTTPS. |
| `apps/backend/main.py` | Login, sesiones, JPEG/MJPEG autenticado, lista de cámaras, eventos e indicadores SQLite. |
| `apps/frontend/` | React/TS, login, selector/mosaico, reproducción, eventos e indicadores. |
| `infra/docker-compose.yml` | Backend y frontend; proxy frontend ligado solo a `127.0.0.1:8102`. |
| `config/` | Ejemplos Mac, Android, Pi y configuración local ignorada por Git. |
| `AGENTS.md` | Estándares de implementación, privacidad y criterios de aceptación. |

Rutas API: `POST /api/login`, `/api/logout`, `GET /api/me`, `/api/cameras`, `/api/cameras/{id}/snapshot`, `/api/cameras/{id}/stream`, `/api/events`, `/api/insights` (sesión), `POST /api/edge/{id}/frame` (token edge), `GET /api/health`. Los JPEG solo permanecen temporalmente en RAM; eventos e indicadores se almacenan en SQLite con retención de siete días. Un solo worker de backend por su relay en memoria.

## Tests

```bash
python -m pip install -r apps/backend/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py maia_vision apps tests scripts
cd apps/frontend && npm install && npm run build
```

CI no sustituye pruebas de cámaras físicas, TLS, Safari y despliegue. Sigue pendiente MediaMTX/WebRTC, alertas, audio, zonas, grabaciones, PWA y multiusuario/MFA. No atribuir sueño, ansiedad ni identidad de Maia a un detector genérico: `QUIETA` solo indica un desplazamiento aparente pequeño y `NO DETECTADA` significa que el detector no la ve. Revisa licencias de Ultralytics antes de redistribuir/comercializar el producto. No hay licencia propia del proyecto definida.
