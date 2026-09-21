# Despliegue: Mac hoy, Raspberry y VPS después

## Topología de seguridad

- En la casa: webcam Mac o Raspberry con fuentes Android MJPEG y cámaras WiFi RTSP. Solo el agente contacta al VPS mediante una petición HTTPS **saliente**. No publiques HTTP/RTSP de cámaras en el router.
- En el VPS: Docker Compose con Nginx/React (solo `127.0.0.1:8080` del host) y FastAPI/SQLite **no expuesto públicamente**. Un reverse proxy (Caddy/Nginx existente) escucha 443 con certificado válido y enruta a `127.0.0.1:8080`. No expongas el puerto 8080 públicamente.
- Navegadores: web desde el dominio HTTPS, cookie HttpOnly Secure SameSite Strict; frames MJPEG y API protegidos por la misma cookie. HTTPS también cubre las subidas del agente.

## VPS — pasos con datos reales (no están disponibles en el repositorio)

1. Apunta un dominio/subdominio propio al VPS y comprueba puertos 80/443 y certificado TLS. No inventar DNS, IP ni rutas del servidor.
2. Copia el repositorio al VPS. `cp .env.example .env`; `python3 scripts/hash_password.py`, copia línea hash completa y genera 2 secretos diferentes usando `python3 -c 'import secrets; print(secrets.token_hex(32))'` dos veces. Asigna `MAIA_PUBLIC_ORIGIN=https://TU_DOMINIO`, `MAIA_COOKIE_SECURE=true` y los IDs de cámara deseados en `MAIA_CAMERAS_JSON`. Ejecuta `chmod 600 .env`. NUNCA publiques el hash, contraseña, token ni `.env`.
3. Ejecuta `docker compose -f infra/docker-compose.yml up -d --build`; comprueba `curl -fsS http://127.0.0.1:8080/api/health`. Datos SQLite en `data/` (persisten al recrear contenedor).
4. Configura el reverse proxy que ya tengas o usa `infra/Caddyfile.example` como plantilla sustituyendo dominio. No sobreescribas la configuración de otros proyectos del VPS. Para MJPEG, desactiva buffering y permite streams duraderos; Caddy `flush_interval -1` en el ejemplo. Comprueba `https://TU_DOMINIO/api/health` y login con navegador. El origen configurado debe coincidir exactamente con el origen del navegador, sin barra final.
5. Revisa firewall: expuestos solo 80/443 y SSH administrado; localhost:8080 NO público, backend 8000 NO publicado. Prueba acceso desde datos móviles, sesión inválida para imágenes, salida/logout, y restauración de la copia de seguridad SQLite cifrada si la necesitas.

## Mac — desarrollo

Arranca Docker con `.env` de desarrollo (`http://localhost:8080`, cookie secure=false). En un venv aislado instala `apps/edge/requirements.txt`, carga `.env` mediante `set -a; source .env; set +a` en shell **solo si controlas y has revisado el fichero local** y ejecuta `python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8080 --no-vision`. Posteriormente activa YOLO quitando la bandera.

Para desarrollar React por separado: backend nativo `uvicorn apps.backend.main:app --reload --port 8000` con `MAIA_PUBLIC_ORIGIN=http://localhost:5173` y cookie Secure=false; `cd apps/frontend && npm install && npm run dev` (Vite proxifica `/api`). Evita simultanear backend nativo y Docker en puertos superpuestos.

## Raspberry — futura migración

1. Raspberry Pi con sistema ARM64, buena alimentación, refrigeración, SSD recomendado para sistema y suficientes recursos según benchmarks. Instala Python 3.11+ y crea `.venv-edge`; `pip install -r apps/edge/requirements.txt`. PyTorch/Ultralytics para ARM puede necesitar adaptaciones por OS/modelo: valida instalación y FPS reales antes de instalar permanentemente.
2. Crea `edge.env` **solo en la Raspberry** (archivo ignorado), con `MAIA_EDGE_TOKEN=<MISMO_TOKEN_DEL_VPS>` y las variables `MAIA_SALON_URL`, `MAIA_ANDROID_URL`, `MAIA_PASILLO_URL` en red local. Preferir credenciales de cámara distintas y seguras. Ejecuta `chmod 600 edge.env` y `set -a; source edge.env; set +a` desde una shell de confianza.
3. Ejecuta `python -m apps.edge.agent --config config/cameras.raspberry.example.json --backend https://TU_DOMINIO --fps 1 --width 480 --no-vision`. Verifica recepción de las TRES cámaras con vídeo sin YOLO; activa gradualmente modelo y mide CPU, RAM, latencia y temperatura. Usa ID de cámara idénticos a `MAIA_CAMERAS_JSON` en VPS.
4. Cuando el agente funcione, conviértelo en un servicio systemd gestionado mediante un usuario no privilegiado, directorio de trabajo del repo, EnvironmentFile apuntando a `edge.env` protegido y ExecStart con Python de venv. Evita registrar credenciales o URL completas. Define reinicio controlado y prueba recuperación tras reiniciar.

**Este proyecto no despliega por sí mismo sobre tu VPS ni instala apps en un móvil**: esos pasos requieren acceso a tus equipos, DNS, credenciales privadas y validación por tu parte. Las instrucciones anteriores son comandos ejecutables y no implican que hayan sido ejecutados sobre tu infraestructura.

## Escalado posterior

Actualmente el backend procesa JPEG en RAM y trabaja con un único worker Uvicorn; cada agente sube vistas aunque nadie mire el dashboard. Es práctico a 1–3 FPS/cámara pero no equivale a stream HD de 30 FPS ni permite escalar a múltiples réplicas. Para calidad elevada separar media: RTSP local→MediaMTX→WebRTC/HLS, privacidad con autentificación propia de streams e infraestructura ICE/TURN si es necesaria. Requiere más pruebas de redes domésticas, Android/iPhone y coste de ancho de banda, y queda como fase posterior.
