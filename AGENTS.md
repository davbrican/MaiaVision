# AGENTS.md — Contrato de desarrollo MaiaVision

## Objetivo

MaiaVision monitoriza actividad observable de un perro mediante una o varias cámaras y permite visualizar capturas en una web privada. Usuario: David; mascota: Maia. No está relacionado con el proyecto de semáforos. Soportar webcam Mac **ahora**, Android WiFi, RTSP/MJPEG IP y Raspberry **sin rediseñar la API**. Revisar `README.md` y `docs/` antes de editar; NO confundir planificado con implementado.

## Arquitectura actual (implementada en código, no validada en hardware/VPS)

1. `apps/edge/agent.py`: un proceso local Mac/Raspberry con un hilo por cámara y captura OpenCV desde `config/*.json`; URL fuente mediante `source_env`, nunca hardcodear secretos. YOLO compartido con lock opcional `--no-vision`, ActivityTracker **independiente por fuente**. Reencuadra a `--width`, comprime JPEG, envía 1-5 FPS por HTTPS saliente al VPS con `MAIA_EDGE_TOKEN`. Si se pierde la señal, libera y reconecta. Un archivo de vídeo de prueba acaba en EOF.
2. `apps/backend/main.py`: FastAPI de **un único worker**, cámaras permitidas por `MAIA_CAMERAS_JSON`; sesiones firmadas con HMAC, contraseña PBKDF2, cookie HttpOnly/SameSite Strict/Secure, validación de Origin en POST web, limitación de login por IP, token separado edge. Retiene último fotograma **solo en RAM**, entrega MJPEG/Snapshot detrás de login, persiste SOLO eventos SQLite 7 días.
3. `apps/frontend`: React TypeScript responsive, inicio de sesión, mosaico/selector de cámaras, estados, eventos y cierre de sesión. Imágenes consumen endpoints autenticados mismo origen; no incrustar URL IP privada del Android en el navegador.
4. `infra/docker-compose.yml`: servicios backend + frontend Nginx. Puerto del frontend expuesto únicamente en loopback VPS `127.0.0.1:8080`; en producción el proxy Caddy/Nginx externo termina TLS. No exponer API directamente. La DB persiste en `data/` ignorada.
5. `main.py` y `maia_vision/`: monitor anterior solo local y detector/tracker reutilizados. Mantener CLI legado estable salvo migración probada.

**No implementado:** MediaMTX/WebRTC/HLS, streaming HD/30 FPS, audio o ladridos, zonas, alertas, PWA instalable/offline, reconocimiento individual de Maia, identificación multi-perro, descubrimiento automático ONVIF, MFA/multiusuario, configuración editada desde UI, grabaciones o despliegue real en un VPS. No afirmar lo contrario.

## Seguridad — obligaciones innegociables

- JAMÁS commitear `.env`, `edge.env`, hashes de contraseña reales, tokens, imágenes de la casa, IP privadas con credenciales, URLs RTSP reales, bases de datos, peso YOLO ni vídeos personales. `.gitignore` cubre datos y ejemplos deben contener valores falsos.
- Publicar web remota solo con HTTPS y cookie `Secure=true`. La excepción HTTP es `localhost` para desarrollo. No abrir puertos de Android/RTSP ni del router; edge establece conexiones salientes. Cuando cambie el servidor de vídeo, cada flujo deberá seguir autenticado (login de React **no** protege por sí solo un puerto MediaMTX expuesto).
- Validar el ID de cámara con allowlist y token antes de almacenar frames; limitar tamaños. No devolver rutas, contraseñas o tokens a frontend. Mantener rate limit de login, cookies HttpOnly, SameSite, origin guard y cabeceras de no caché; añadir pruebas si cambian.
- Proteger privacidad: no grabación continua por defecto, retención de 7 días para eventos, consentir observación de personas presentes. Evitar descargar modelos durante tests CI.
- El edge guarda URL solo en variable entorno; no imprimir URL, cabeceras de autenticación ni excepción con parámetros privados en logs.
- Comprometer cambios a ramas de feature y PR revisable; no fusionar en `main` sin aprobación explícita. No desplegar VPS sin URL, entorno, credenciales y autorización del usuario.

## Reglas de calidad

- Python 3.11+; TS estricto; código tipado, funciones delimitadas, tests para seguridad, ingestión, validaciones y tracker sin cámara/YOLO; CI `unittest`, `compileall`, `npm run build`.
- Un tracker por cámara, detector opcional compartido protegido con lock. Nunca confundir «detección más confiable» con identidad real del perro. `NO DETECTADA` ≠ fuera de habitación; `QUIETA` ≠ dormida; píxeles/s ≠ m/s.
- Revisar configuraciones de cámara usando IDs idénticos en `MAIA_CAMERAS_JSON` y `config/*.json`. Fallar con error claro si faltan URLs o tokens, sin secretos en errores.
- Recursos: liberar `VideoCapture`, `requests.Session`, hilos, sockets y archivos; no ejecutar `cv2.imshow` en proceso headless. Evitar abrir dos veces la webcam física para detector y streaming.
- `EventStore` SQLite no graba frames; relay en RAM requiere **exactamente un worker** de backend. Para escalado usar MediaMTX + broker compartido. Controlar ancho de banda ~FPS × tamaño JPEG × cámaras: vídeo remoto en baja frecuencia **no** se llama streaming HD.
- README y docs en español; eventos y rutas con nombres ingleses estables. No introducir configuración ficticia ni prometer que Raspberry soporta 3 YOLO simultáneos sin benchmarking.

## Aceptación / validación

1. Arranque Docker sin variables reales debe FALLAR (fail closed). Con `.env` correcto, API healthy, UI sirve login y lista cámaras offline.
2. Sin cookie, `GET /api/cameras`, `snapshot`, `stream` y `/events` devuelven 401. Contraseña incorrecta 401; Origin ausente/extraño 403; logout revoca cookie en navegador.
3. El token edge es independiente de cookie; cámara desconocida 404; JPG corrupto/mayor de 500 kB rechazado. Frames válidos cambian estado; snapshots autenticados y eventos persistidos.
4. Webcam y Android en una misma red se abren con configuración sin modificar código. Cámara desconectada se marca offline después de 20 s; CLI cierra con Ctrl+C. Comprobar manualmente con hardware.
5. Front compila TypeScript y permite login, selección única/mosaico, visualización y eventos sin conocer la URL privada de cámaras; validar móvil/Safari manualmente.
6. En VPS real: HTTPS y cookies Secure, Nginx/Caddy proxy streaming sin buffering, proxy escucha localhost; comprobar acceso desde red móvil, sin URL de cámara expuesta, y dimensionar ancho de banda.
7. Fases futuras en PR separado: MediaMTX autenticado + WebRTC/HLS, PWA, historial configurable, zonas, audio opt-in, alertas, permisos por usuario. No mezclar features no probadas en este MVP.

## Comandos

```bash
python -m pip install -r apps/backend/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py maia_vision apps tests scripts
cd apps/frontend && npm install && npm run build
# Arranque: cp .env.example .env; python scripts/hash_password.py;
# docker compose -f infra/docker-compose.yml up -d --build
# Edge: python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8080 --no-vision
```

**Contexto de hardware:** el agente puede correr Mac hoy, Raspberry ARM64 en el futuro cuando se instale; no añadir Docker con acceso a cámara Apple que no funcione. Android requiere aplicación compatible con MJPEG/RTSP en WiFi, IP local y fuente real validada. Si no se dispone de hardware ni acceso al VPS, declarar la verificación pendiente.
