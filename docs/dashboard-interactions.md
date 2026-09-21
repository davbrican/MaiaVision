# Controles de cámara del dashboard

Versión desarrollada en `feat/web-dashboard-multicamera-android` / PR #1. No afecta a Nginx, configuración del agente, IDs, puertos ni `.env`.

## Uso

1. Abre `https://maiavision.dbrincau.com` e inicia sesión.
2. En **Todas**, pulsa o toca cualquier imagen (incluso una cámara desconectada) para abrir su vista individual. Es equivalente al botón con el nombre de esa cámara.
3. En la vista individual, pulsa la imagen o **⛶ Ampliar** para entrar en pantalla completa. Pulsa la imagen de nuevo, el botón **✕ Salir** o `Esc` (cuando proceda) para salir. En navegadores que no admiten la Fullscreen API para elementos arbitrarios, como ciertas versiones de Safari en iPhone, se utiliza una vista ampliada dentro de la propia página.
4. Pulsa **📸 Captura** para solicitar `/api/cameras/{id}/snapshot`, usando tu cookie de sesión. Se descarga un JPEG del último fotograma recibido, con nombre `maiavision-ID-FECHA.jpg`; no es una fotografía en máxima resolución de la cámara IP ni necesariamente idéntica al instante que ves en la transmisión MJPEG. La descarga puede variar según el navegador móvil; si no aparece en la galería, comprueba Descargas/Archivos.
5. El botón de captura está desactivado cuando la cámara no tiene señal. Si expira la sesión o no hay una imagen reciente, se muestra un error sin guardar nada.
6. Regresa al mosaico pulsando **Todas** en el selector superior.

## Privacidad y limitaciones

- Las capturas solo se solicitan tras pulsar el botón: **no** hay grabación automática ni almacenamiento de capturas en el VPS. El usuario decide conservar el JPEG descargado en su propio dispositivo. Evita compartir imágenes de la vivienda o de personas sin permiso.
- El servidor conserva únicamente el último JPEG en RAM para cada cámara; el endpoint snapshot ya existía y exige autenticación. Los flujos MJPEG también requieren sesión.
- Fullscreen **no mejora la resolución** original de los fotogramas del agente. Para mayor detalle, ajusta `--width` y comprueba CPU/red. No promete vídeo HD ni 30 FPS.
- En iOS, una vista CSS a pantalla completa puede seguir mostrando algunos controles del navegador; no equivale necesariamente al modo nativo del sistema operativo.
- Las cámaras desconectadas siguen siendo seleccionables para consultar estado, pero no pueden producir una captura válida.

## Validación manual recomendada

- Escritorio: mosaico → cámara individual → fullscreen → salir con botón/Esc → Todas.
- Móvil iOS/Android: mosaico y vista individual, fallback sin desbordamientos, botones táctiles, capturas en Archivos/Descargas.
- Cámaras offline: se puede abrir vista individual, captura deshabilitada.
- Sesión caducada: snapshot no descarga datos privados y muestra error.
- El cambio solo afecta al frontend; tras actualizar el VPS, reconstruye con `docker compose -f infra/docker-compose.yml up -d --build` y recarga la web.
