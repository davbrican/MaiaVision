# Sustituir el Mac por otro ordenador (sin tocar el VPS)

Servidor ya desplegado: `https://maiavision.dbrincau.com` → Nginx host → `127.0.0.1:8102` → frontend/API Docker. **El puerto 8102 solo existe en el VPS; el agente SIEMPRE apunta al dominio HTTPS, sin puerto.** Los fotogramas llegan mediante conexiones salientes. El Android y el ordenador nuevo deben estar en la misma LAN/WiFi, o conectados por una VPN privada que alcance las cámaras. No abras el puerto del Android al exterior.

## Ubuntu/Debian 64 bits — comandos EN ORDEN

Ejecuta todo en el **ordenador nuevo**, con un usuario normal con `sudo`, no en el VPS.

### A. Preparar el sistema y clonar

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ca-certificates
python3 --version  # requiere Python 3.11 o posterior
cd ~
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
git pull --ff-only
python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/edge/requirements.txt
```

Si la versión de Python es anterior a 3.11, instala una versión soportada primero. Si falla la instalación de PyTorch/Ultralytics en ARM (especialmente Raspberry), resuelve wheels específicos del sistema y prueba primero `--no-vision`: no afirmamos compatibilidad automática. La primera carga del modelo puede descargar pesos con acceso a Internet.

### B. Guardar solo los secretos del agente

```bash
cd ~/MaiaVision
umask 077
nano edge.env
```

Contenido de `edge.env` (sustituye valores **localmente**, no lo compartas):

```dotenv
MAIA_EDGE_TOKEN='PEGA_AQUI_EL_TOKEN_ACTUAL_DEL_VPS'
MAIA_BACKEND_URL='https://maiavision.dbrincau.com'
MAIA_ANDROID_URL='http://IP_REAL_DEL_ANDROID:PUERTO/RUTA_REAL_DE_VIDEO'
```

Usa la URL del stream comprobada desde el navegador de este ordenador; en IP Webcam suele ser `/video`, pero comprueba versión e interfaz. En el VPS puedes consultar *privadamente* el token de `~/MaiaVision/.env`; nunca copies TODO ese `.env` al dispositivo ni incluyas el hash de admin o `MAIA_SESSION_SECRET`. Si rotas el token en el VPS, deberás actualizar todos los agentes que lo utilicen. Protege el archivo:

```bash
chmod 600 edge.env
set -a
source ./edge.env
set +a
```

`source` ejecuta un archivo de shell: hazlo únicamente con este archivo local que tú has creado y revisado. No imprimas el token en los logs ni en chats.

### C. Verificar el servidor y el vídeo Android

```bash
curl -fsS https://maiavision.dbrincau.com/api/health
```

Debe mostrar `{"status":"ok"}`. Comprueba la URL del Android abriéndola desde este ordenador en un navegador o VLC; no publiques URLs con credenciales.

### D. Elegir las cámaras y probar SIN reconocimiento

Solo Android, **sin webcam USB**, aunque el ordenador no tenga ninguna:

```bash
python -m apps.edge.agent \
  --config config/cameras.android-only.example.json \
  --backend https://maiavision.dbrincau.com \
  --fps 2 --width 640 --no-vision
```

Con webcam USB/portátil de índice `0` **y Android al mismo tiempo**:

```bash
python -m apps.edge.agent \
  --config config/cameras.android.example.json \
  --backend https://maiavision.dbrincau.com \
  --fps 2 --width 640 --no-vision
```

La cámara índice 0 puede ser otra en Linux; comprueba `ls -l /dev/video*` y permisos del grupo `video` si falla. Cuando el mosaico funcione, `Ctrl+C` y repite el comando SIN `--no-vision` para activar YOLO. En Linux sin pantalla no se necesita entorno gráfico. Si el equipo tiene poca potencia, usa `--fps 1 --width 480`. El porcentaje de actividad y la última detección requieren YOLO; con `--no-vision` se ve imagen, pero NO se generan métricas de perro.

**Migración segura:** detén el proceso anterior del Mac con `Ctrl+C` ANTES de arrancar el proceso definitivo en el nuevo PC. Dos agentes enviando la misma ID `android` o `webcam` se pisarían entre sí. En el dashboard puede quedar `webcam` sin señal si has elegido Android solamente; es normal hasta cambiar la allowlist del VPS de forma consciente.

### E. Arranque automático con systemd (Ubuntu/Debian, opcional)

Primero detén con `Ctrl+C` el comando manual. Con un usuario normal ejecuta desde `~/MaiaVision`:

```bash
sudo tee /etc/systemd/system/maia-edge.service >/dev/null <<EOF
[Unit]
Description=MaiaVision Edge Agent
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/MaiaVision
EnvironmentFile=$HOME/MaiaVision/edge.env
ExecStart=$HOME/MaiaVision/.venv-edge/bin/python -m apps.edge.agent --config config/cameras.android-only.example.json --backend https://maiavision.dbrincau.com --fps 2 --width 640
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now maia-edge
sudo systemctl status maia-edge --no-pager
```

Si usas dos cámaras, cambia `config/cameras.android-only.example.json` por `config/cameras.android.example.json` en la línea `ExecStart` ANTES de crear el servicio. Logs: `sudo journalctl -u maia-edge -n 60 --no-pager`. Parada: `sudo systemctl stop maia-edge`. No pongas las URLs privadas ni el token directamente en `ExecStart`.

## Si el ordenador nuevo es macOS

Instala Git y Python 3.11+ (por ejemplo mediante Homebrew), y desde la sección A utiliza `python3`/`python3.11` para crear el venv, `source .venv-edge/bin/activate`, `python -m pip ...`. Las secciones B–D y la configuración de cámaras son iguales. No utilices systemd en macOS; para arranque automático se requiere un LaunchAgent/LaunchDaemon específico y permisos de cámara.

## Si el ordenador nuevo es Windows 11 (PowerShell)

Instala Git y Python 3.11+ y comprueba `git --version` y `py -3.11 --version`. Desde PowerShell:

```powershell
cd $HOME
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
py -3.11 -m venv .venv-edge
.\.venv-edge\Scripts\python.exe -m pip install --upgrade pip
.\.venv-edge\Scripts\python.exe -m pip install -r apps/edge/requirements.txt
$secure = Read-Host 'Token EDGE del VPS' -AsSecureString
$env:MAIA_EDGE_TOKEN = [System.Net.NetworkCredential]::new('', $secure).Password
$env:MAIA_ANDROID_URL = 'http://IP_REAL:PUERTO/RUTA_REAL'
.\.venv-edge\Scripts\python.exe -m apps.edge.agent --config config/cameras.android-only.example.json --backend https://maiavision.dbrincau.com --fps 2 --no-vision
```

Quita `--no-vision` cuando funcione el vídeo. Si hay webcam y Android, cambia al archivo `cameras.android.example.json`. En Windows usa el Programador de tareas para autoarranque, evitando contraseñas o tokens en el comando o en argumentos visibles; prueba primero manualmente.

## Para actualizar a la versión con indicadores

En el VPS (solo despliega MaiaVision, sin tocar los otros contenedores):

```bash
cd ~/MaiaVision
git switch feat/web-dashboard-multicamera-android
git pull --ff-only
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://127.0.0.1:8102/api/health
```

No recrees `.env`, no vuelvas a generar secretos y no ejecutes `docker compose down -v`. La nueva tabla `activity_samples` se crea automáticamente en el SQLite existente; recopila únicamente metadatos, una muestra por cámara cada ~10 s, con retención de siete días. El pasado anterior a la actualización NO se reconstruye. Acceso a indicadores: dashboard habitual, tras iniciar sesión. El endpoint `/api/insights` requiere cookie de login.
