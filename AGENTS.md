# AGENTS.md — Contrato de desarrollo MaiaVision

## Propósito y estado

MaiaVision es un monitor privado de mascotas para David y Maia. Reconoce perros genéricos, no la identidad individual de Maia. Webcam Mac ahora, Android WiFi, cámaras RTSP/MJPEG y migración futura a Raspberry sin alterar API. No está relacionado con el proyecto de semáforos. Leer `README.md` y `docs/` antes de editar; distinguir siempre implementado de planificado.

Versión multicámara en rama `feat/web-dashboard-multicamera-android` / PR #1. Tests de Python/API y build React en CI; despliegue y pruebas reales de cámara/Mac/Pi/VPS pendientes. Trabajar en rama de feature y PR; no fusionar `main` sin aprobación.

## Arquitectura actual

1. `apps/edge/agent.py`: proceso nativo Mac/Raspberry, un hilo por fuente OpenCV `config/*.json` (webcam, Android MJPEG/RTSP, cámaras RTSP, fichero). URLs mediante `source_env` privadas. Detector YOLO opcional y compartido con lock; `ActivityTracker` independiente por cámara; JPEG reducido enviado por HTTPS saliente con `MAIA_EDGE_TOKEN` a `https://maiavision.dbrincau.com/api/edge/{id}/frame`. Reconexión y liberación de recursos; el fichero acaba en EOF.
2. `apps/backend/main.py`: FastAPI **un worker**, allowlist `MAIA_CAMERAS_JSON`, contraseña PBKDF2, sesión HMAC en cookie HttpOnly/SameSite Strict/Secure, comprobación Origin, limitación intentos, token edge separado. Último fotograma únicamente en RAM, snapshot/MJPEG autenticado, eventos SQLite durante 7 días. No exponer backend al host.
3. `apps/frontend`: React/TypeScript responsive; login, selector/mosaico, cámara y eventos por API del mismo origen. Jamás enviar URL privada del Android al navegador.
4. `infra/docker-compose.yml`: API interna puerto `8000` **sólo Docker**; frontend interno `80` publicado como **`127.0.0.1:8102:80` en host**. El VPS ya dispone de Nginx propio; dominio `maiavision.dbrincau.com` (HTTPS 443) debe hacer proxy a `http://127.0.0.1:8102`. No instalar otro Nginx/Caddy en puertos 80/443 ni tocar sitios de otros proyectos. `MAIA_PUBLIC_ORIGIN=https://maiavision.dbrincau.com` y `MAIA_COOKIE_SECURE=true` en VPS. 8102 NO se publica en Internet. El 8080 eventual de IP Webcam es exclusivamente un puerto LAN del Android, ajeno al puerto del VPS.
5. `main.py` / `maia_vision/`: CLI local legado y lógica compartida, conservar compatibilidad.

## Reglas de seguridad

- Nunca publicar ni commitear `.env`, `edge.env`, hashes reales, tokens, capturas domésticas, URLs RTSP reales/credenciales, bases de datos, pesos YOLO, vídeos personales. `data/` y secretos ignorados. El agente de casa abre cámaras locales; únicamente el agente contacta el VPS por HTTPS **saliente**, sin abrir el router doméstico.
- Requerir HTTPS real y cookie Secure antes de exponer dominio. HTTP localhost sólo desarrollo. Una sesión React no protege automáticamente flujos de otro servidor: si se añade MediaMTX, autenticar TODOS los streams. Proteger endpoints de frames con token y allowlist, limitar tamaño, impedir fuga de IP/secretos en logs/respuestas, usar cabeceras no-cache.
- Comprobar disponibilidad de puerto 8102 también con `ss -ltnp`, no sólo `docker ps`; no interferir con otros contenedores. Antes de reiniciar Nginx: `nginx -t`. No efectuar despliegue remoto sin acceso/credenciales/autorización real.
- Retener eventos 7 días, no grabar vídeo/audio/imágenes por defecto; fotogramas temporalmente en RAM del backend. Informar a personas que puedan aparecer. Tests CI nunca descargan modelo ni abren cámara.
- No atribuir estados emocionales ni diagnósticos: `NO DETECTADA` ≠ fuera de casa; `QUIETA` ≠ dormida; píxeles/s ≠ velocidad real; detector de perro ≠ identificador de Maia.

## Desarrollo y calidad

- Python 3.11+, TypeScript estricto. Funciones tipadas, tests de seguridad, ingestión, estados y validaciones sin hardware. Un tracker por cámara y detector YOLO opcional compartido bajo lock. Liberar VideoCapture, sesión requests y threads. No abrir webcam desde dos procesos simultáneos.
- IDs deben coincidir entre `MAIA_CAMERAS_JSON` y `config/*.json`. Rechazar secretos de ejemplo, URL ausentes, IDs desconocidos y JPEG inválidos. Secretos nunca en JSON versionados.
- Un solo worker Uvicorn: los fotogramas están en RAM local del proceso. No escalar réplicas sin relay compartido. Documentar FPS, latencia, ancho de banda y uso CPU en Mac/Pi; no afirmar 3 inferencias en Pi sin benchmark.
- Nombres de rutas y eventos estables en inglés; README y guías en español. Actualizar comandos de docs al cambiar puertos. Si falla la cámara real o no hay acceso al VPS, indicar validación pendiente.

## Criterios de aceptación

1. Sin secretos reales, arranque debe fallar (fail closed). Con `.env` correcto, `/api/health` accesible localmente por `127.0.0.1:8102`; web privada muestra cámaras offline antes de arrancar edge.
2. Endpoints `/api/cameras`, snapshot, stream y eventos requieren cookie (401 sin ella). Login equivocado 401, Origin incorrecto 403; logout borra sesión. Token edge independiente, ID desconocido 404, JPEG corrupto o >500 kB rechazado.
3. Webcam y Android configurados por variable pueden abrirse simultáneamente sin modificar código, reconectar y cerrar con Ctrl+C; validación manual pendiente. UI responsive permite login, vista única, mosaico, estados y eventos; verificar Safari/iOS con dispositivos reales.
4. VPS: HTTPS válido, `MAIA_PUBLIC_ORIGIN` exactamente igual a dominio, Nginx host hacia `127.0.0.1:8102` sin buffering, Docker sólo liga loopback, acceso desde datos móviles con autenticación, sin revelar URL de cámaras.
5. Mantener fases futuras separadas: MediaMTX/WebRTC/HLS, vídeo HD, PWA, alertas, zonas, audio opt-in y ladridos, MFA/multiusuario, descubrimiento ONVIF, grabaciones o identidad multi-perro **no implementados**.

## Comandos

```bash
python -m pip install -r apps/backend/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py maia_vision apps tests scripts
cd apps/frontend && npm install && npm run build
# VPS: docker compose -f infra/docker-compose.yml up -d --build
# VPS: curl -fsS http://127.0.0.1:8102/api/health
# Mac hacia VPS: python -m apps.edge.agent --config config/cameras.mac.json --backend https://maiavision.dbrincau.com --no-vision
# Mac con Docker local: python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8102 --no-vision
```

El agente en Mac no debe usar `localhost:8102` cuando el backend vive en el VPS. El puerto local de IP Webcam Android sigue siendo independiente. Revisar licencias Ultralytics antes de comercializar el proyecto; no imponer licencia propia sin decisión del titular.
