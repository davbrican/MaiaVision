# Despliegue: Mac hoy, Raspberry y VPS después

## Topología de seguridad

- En casa: webcam del Mac o Raspberry conectada a Android MJPEG y cámaras WiFi RTSP. El agente envía imágenes JPEG y eventos al VPS por peticiones HTTPS **salientes**. No publiques los puertos HTTP/RTSP de cámaras en el router.
- VPS: Docker Compose con Nginx/React escuchando **solo en `127.0.0.1:8102`**, FastAPI/SQLite dentro de la red Docker sin puerto público. Nginx del HOST (ya existente) termina HTTPS 443 y enruta `maiavision.dbrincau.com` a `http://127.0.0.1:8102`.
- Navegadores: dominio HTTPS, cookie HttpOnly Secure SameSite Strict; imágenes MJPEG y API protegidas por la sesión. HTTPS también protege las subidas del agente.
- El `8080` que pudiera mostrar IP Webcam **en el Android** pertenece a la red local y no tiene relación con el `8102` reservado para MaiaVision en el VPS.

## VPS — despliegue en el host con otros proyectos Docker

1. Configura el DNS A/AAAA de `maiavision.dbrincau.com` hacia tu VPS. Antes de desplegar, comprueba que `8102` esté libre tanto en Docker como en los procesos del host: `docker ps --format 'table {{.Names}}\t{{.Ports}}'` y `sudo ss -ltnp | grep ':8102 '`. La ausencia en `docker ps` por sí sola no garantiza disponibilidad.
2. Clona el repositorio y usa la rama `feat/web-dashboard-multicamera-android` hasta que se apruebe y fusione la PR. Ejecuta `cp .env.example .env`, `python3 scripts/hash_password.py` y genera dos secretos **distintos** con `python3 -c 'import secrets; print(secrets.token_hex(32))'`. Configura `MAIA_PUBLIC_ORIGIN=https://maiavision.dbrincau.com`, `MAIA_COOKIE_SECURE=true` y `MAIA_CAMERAS_JSON` con IDs idénticos a las fuentes del agente. Nunca publiques `.env`; ejecuta `chmod 600 .env`.
3. Arranca `docker compose -f infra/docker-compose.yml up -d --build` desde la raíz del repo y verifica `curl -fsS http://127.0.0.1:8102/api/health`. La base SQLite persiste en `data/`. Docker publica únicamente `127.0.0.1:8102:80` para frontend; el `8000` de FastAPI se expone solo internamente y puede coexistir con otros contenedores que utilicen 8000.
4. Reutiliza el Nginx existente del host; no instales otro proxy ni sobrescribas configuraciones ajenas. Crea un bloque `server_name maiavision.dbrincau.com` que, tras habilitar TLS, use esta sección (integrada en el bloque HTTPS correspondiente):

```nginx
location / {
    proxy_pass http://127.0.0.1:8102;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 3600s;
}
```

5. Verifica `sudo nginx -t` **antes** de recargar con `sudo systemctl reload nginx`. Obtén o renueva certificado HTTPS según el procedimiento vigente del host (por ejemplo Certbot, si ya lo utilizas). Comprueba `https://maiavision.dbrincau.com/api/health`, login y visualización desde datos móviles. `MAIA_PUBLIC_ORIGIN` debe coincidir exactamente con `https://maiavision.dbrincau.com` (sin `/api`, sin puerto, sin barra final).
6. No publiques `8102` en el firewall; sólo Nginx expone 80/443 y SSH administrado. Prueba que un navegador sin login no pueda ver imágenes ni eventos; revisa logout, cookies Secure y copias cifradas de SQLite si las necesitas.

## Mac — ejecutar edge apuntando al VPS

Concede permiso de cámara a Terminal/iTerm. Crea un venv, instala `apps/edge/requirements.txt` y exporta **solo en tu Mac** `MAIA_EDGE_TOKEN` (el mismo valor secreto del VPS), y opcionalmente `MAIA_ANDROID_URL` con la URL de vídeo del Android accesible por la misma WiFi. Arranca:

```bash
python -m apps.edge.agent --config config/cameras.mac.json --backend https://maiavision.dbrincau.com --fps 2
# O webcam + Android:
python -m apps.edge.agent --config config/cameras.android.example.json --backend https://maiavision.dbrincau.com --fps 2
```

Usa `--no-vision` si quieres probar primero envío sin YOLO. **Nunca apuntes el agente del Mac a `127.0.0.1:8102` si el backend está en el VPS**: esa dirección indicaría el propio Mac. El agente utiliza el dominio público por HTTPS; `8102` sólo es el destino interno del proxy del VPS.

Para desarrollo enteramente local: `.env` con `MAIA_PUBLIC_ORIGIN=http://localhost:8102` y `MAIA_COOKIE_SECURE=false`, arranca Docker y usa `--backend http://localhost:8102`. El frontend con Vite por separado funciona en 5173 y el backend nativo en 8000 sólo si esos puertos están libres.

## Raspberry — futura migración

1. Raspberry Pi ARM64, alimentación, refrigeración y SSD opcional. Instala Python 3.11+, venv y `apps/edge/requirements.txt`; valida PyTorch/Ultralytics en su OS y mide FPS, RAM y temperatura antes de activar inferencia de tres cámaras.
2. Crea `edge.env` privado con `MAIA_EDGE_TOKEN` y `MAIA_SALON_URL`, `MAIA_ANDROID_URL`, `MAIA_PASILLO_URL` locales; `chmod 600 edge.env`. IDs idénticos a `MAIA_CAMERAS_JSON`.
3. Ejecuta `python -m apps.edge.agent --config config/cameras.raspberry.example.json --backend https://maiavision.dbrincau.com --fps 1 --width 480 --no-vision`, valida las tres cámaras sin YOLO y después habilita detección gradualmente.
4. Usa `infra/maia-edge.service.example` como plantilla systemd con usuario sin privilegios, rutas reales y EnvironmentFile protegido. No guardes contraseñas en el repositorio.

**No se ha desplegado automáticamente en el VPS ni probado con las cámaras físicas.** Esta guía no implica acceso a tu servidor. La retransmisión actual es JPEG/MJPEG en memoria a baja frecuencia con un solo worker; MediaMTX/WebRTC, grabaciones y streaming HD son fases futuras.
