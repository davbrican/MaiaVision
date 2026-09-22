# MaiaVision: instalación de tres Tapo C200C y control PTZ

**Estado:** código integrado en la rama `feat/web-dashboard-multicamera-android` (PR #1). Tests de API/configuración y build ejecutados en CI; **el vídeo, la respuesta ONVIF, la orientación real y el uso de CPU con tres cámaras NO se pueden validar sin las tres C200C y el Mac reales**. No se ha desplegado nada desde GitHub en el VPS doméstico. No fusionar `main` sin revisión.

## Qué implementamos

- Rotación **por cámara** `rotation: 0 | 90 | 180 | 270`, aplicada por OpenCV **antes** de YOLO, anotaciones, JPEG y capturas, también válida para Android/webcam.
- PTZ opcional ONVIF para fuentes RTSP. Cuatro botones y parada en la vista individual; solo aparecen cuando hay señal y un agente PTZ local ha anunciado su disponibilidad recientemente. Toque = desplazamiento breve, no movimiento mantenido, ni seguimiento automático de Maia, ni posiciones guardadas.
- Órdenes autenticadas de sesión con comprobación de origen; cola acotada en memoria del VPS y órdenes caducadas en 3 segundos. El agente hace peticiones **HTTPS salientes** y ejecuta ONVIF en la LAN. El VPS **no** conoce IP, URL RTSP, usuario ni contraseña de Tapo. La respuesta de la API confirma **encolado, no movimiento físico completado**.
- Durante un giro y 3 s de estabilización se suspende la observación del perro para **esa cámara** (estado `SIN ANALISIS`), evitando falsos eventos de movimiento por desplazamiento del encuadre.
- El vídeo sigue siendo JPEG/MJPEG de baja frecuencia. Sin grabación, audio, PWA o control del hardware desde el VPS.

Fuentes del fabricante: [RTSP y ONVIF, credenciales, puertos y limitaciones](https://www.tapo.com/es/faq/34/), [FAQ ONVIF/RTSP](https://www.tp-link.com/es/support/faq/4465/), [firmware específico C200C por región/hardware](https://www.tp-link.com/es/support/download/tapo-c200c/), [imagen invertida](https://www.omadanetworks.com/es/support/faq/2625/). TP-Link indica RTSP 554, ONVIF 2020. Una unidad real y su firmware deben confirmar si expone *ContinuousMove* y acepta órdenes desde `onvif-zeep`; si no, no afirmar que las flechas funcionen.

## Paso 0. Antes de modificar nada

- Conecta las cámaras a **enchufes**: C200C no lleva batería. WiFi y alimentación son cosas diferentes. Conéctalas solo a red doméstica de confianza; **no** abras puertos 554/2020 en el router ni configures reenvío hacia ellas.
- Para evitar gastar dinero y tiempo configurando tres unidades defectuosas/incompatibles, verifica primero **una** hasta que llegue a la sección «Prueba de controles»; luego repite para las otras.
- Haz copia **privada y local** de `~/MaiaVision/.env` del VPS y `~/MaiaVision/edge.env` y `config/cameras.local.json` del Mac, solo si ya existen. Nunca subas copias ni secretos a GitHub ni los pegues en chats. No ejecutes `docker compose down -v`.
- Mantén los mismos identificadores de Android/webcam en la lista del VPS si vas a seguir utilizándolos. Si quieres reemplazarlos con las Tapo, puedes borrarlos de `MAIA_CAMERAS_JSON` **después** de comprobar que las Tapo funcionan; no cambies el token de agente por el mero hecho de cambiar cámaras.

## Paso 1. Preparar cada C200C (en casa, en la app Tapo)

1. Enchufa Tapo 1, inicialízala desde la app, conéctala a la WiFi doméstica y **actualiza su firmware** para su región y versión de hardware. Repite para 2 y 3 cuando la primera funcione.
2. Crea una **cuenta de cámara** local en los ajustes avanzados de Tapo. No es la contraseña de tu cuenta en la nube de TP-Link. Usa credenciales fuertes; puedes utilizar credenciales distintas en las tres para aislar incidencias.
3. Anota **privadamente** la IP LAN asignada a cada cámara y reserva esa IP por DHCP en tu router. Ejemplos: `192.168.1.150`, `.151`, `.152`; **no copies estas direcciones sin conocer las reales**.
4. Si va montada boca abajo en el techo, activa «Imagen invertida» en los ajustes Tapo de esa cámara. Comprueba en VLC que el RTSP también se ve derecho. Si no, deja `rotation: 180` en el agente, **pero no hagas ambas rotaciones**.
5. Desde el **Mac**, verifica vídeo RTSP en VLC: `rtsp://USUARIO:CONTRASEÑA@IP_REAL:554/stream1`. El substream `/stream2` puede reducir carga. Si tu contraseña tiene caracteres reservados para URL (por ejemplo `@`, `#`, `:`), codifícalos correctamente en la URL mediante percent-encoding; no debilites la contraseña para evitarlo.
6. Verifica la integración ONVIF por separado con un cliente como Agent DVR/ONVIF Device Manager apuntando al host LAN, puerto **2020** y **cuenta de cámara**. Comprueba arriba, abajo, izquierda, derecha y Stop. La declaración ONVIF o ver vídeo RTSP no garantizan que *tu firmware* permita cada comando.

## Paso 2. Actualizar primero el VPS

**En SSH al VPS, NO en el Mac:**

```bash
cd ~/MaiaVision
git status --short
git switch feat/web-dashboard-multicamera-android
git pull --ff-only
```

Si hay modificaciones locales sin confirmar, revísalas antes del pull: nunca sobrescribas `.env`, BD ni configuraciones privadas. Abre el `.env` existente:

```bash
nano .env
```

Edita **únicamente** la línea `MAIA_CAMERAS_JSON`. Ejemplo con webcam y ambos Android conservados, además de las tres nuevas:

```dotenv
MAIA_CAMERAS_JSON='{"webcam":"Mac","android":"Android 1","android2":"Android 2","tapo1":"Salón","tapo2":"Pasillo","tapo3":"Dormitorio"}'
```

**Adapta la lista a tus IDs reales:** no introduzcas IDs duplicados, ni elimines cámaras que quieras mantener. Solo se permiten hasta 12. No guardes credenciales/URL de las Tapo en `.env` del VPS. Con `tapo1`, `tapo2`, `tapo3` nuevos, el VPS las mostrará offline hasta que el Mac envíe imágenes.

```bash
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
curl -fsS http://127.0.0.1:8102/api/health
curl -fsS https://maiavision.dbrincau.com/api/health
```

El backend lleva la cola PTZ en RAM; si lo reinicias se descartan órdenes anteriores. La base de datos SQLite y los tokens existentes no deben borrarse. **No** toques Nginx, el dominio, los puertos de la aplicación ni otros contenedores. Si falla, consulta `docker compose -f infra/docker-compose.yml logs --tail=100 backend frontend`. La versión del backend debe desplegarse antes que el agente nuevo si vas a activar PTZ.

## Paso 3. Actualizar el Mac/ordenador Edge

**En el Mac, NO en el VPS:**

1. Detén el agente manual previo con `Ctrl+C`. Si usas un servicio, detenlo en lugar de arrancar dos agentes para la misma cámara. La webcam del Mac solo puede abrirse desde un proceso a la vez.
2. Actualiza el código e instala la dependencia ONVIF **opcional**. Si ya tienes entorno virtual, reutilízalo:

```bash
cd ~/MaiaVision
git status --short
git switch feat/web-dashboard-multicamera-android
git pull --ff-only
# Solo si .venv-edge no existe:
# python3 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install -r apps/edge/requirements.txt
python -m pip install -r apps/edge/requirements-ptz.txt
```

Si `pip install` de ONVIF falla, no declares PTZ habilitado: investiga el error/compatibilidad del Python local. Las cámaras RTSP pueden seguir funcionando **sin** PTZ si retiras su bloque `ptz` del JSON. `onvif-zeep` es una dependencia de terceros antigua; validar su funcionamiento con la versión real de Python y firmware sigue pendiente.

## Paso 4. Secretos y URL *solo* en `edge.env` del Mac

Edita el archivo existente con `nano edge.env`. **Conserva** el `MAIA_EDGE_TOKEN` vigente, `MAIA_BACKEND_URL` si lo tienes y las entradas Android existentes. Añade estas variables utilizando los **datos reales** de cada una de las tres cámaras; el siguiente bloque es una plantilla, NO tres IP descubiertas ni contraseñas reales:

```dotenv
MAIA_TAPO1_HOST='192.168.1.150'
MAIA_TAPO1_USER='USUARIO_LOCAL_1'
MAIA_TAPO1_PASSWORD='CLAVE_LOCAL_1'
MAIA_TAPO1_RTSP='rtsp://USUARIO_LOCAL_1:CLAVE_URL_1@192.168.1.150:554/stream1'

MAIA_TAPO2_HOST='192.168.1.151'
MAIA_TAPO2_USER='USUARIO_LOCAL_2'
MAIA_TAPO2_PASSWORD='CLAVE_LOCAL_2'
MAIA_TAPO2_RTSP='rtsp://USUARIO_LOCAL_2:CLAVE_URL_2@192.168.1.151:554/stream1'

MAIA_TAPO3_HOST='192.168.1.152'
MAIA_TAPO3_USER='USUARIO_LOCAL_3'
MAIA_TAPO3_PASSWORD='CLAVE_LOCAL_3'
MAIA_TAPO3_RTSP='rtsp://USUARIO_LOCAL_3:CLAVE_URL_3@192.168.1.152:554/stream1'
```

`MAIA_TAPO*_PASSWORD` contiene la clave literal para ONVIF; la contraseña insertada en la **URL RTSP** debe percent-encodearse cuando contenga caracteres especiales. No hay variables para el VPS relativas a esas credenciales. Protege el archivo y cárgalo en el terminal actual sin imprimir valores:

```bash
chmod 600 edge.env
set -a
source ./edge.env
set +a
python - <<'PY'
from pathlib import Path
import json, os
for i in (1, 2, 3):
    names = [f'MAIA_TAPO{i}_{suffix}' for suffix in ('HOST','USER','PASSWORD','RTSP')]
    print(f'Tapo {i}:', 'variables completas' if all(os.getenv(n) for n in names) else 'faltan variables')
print('Token:', 'definido' if os.getenv('MAIA_EDGE_TOKEN') else 'FALTA')
PY
```

Nunca pegues aquí el resultado de `cat edge.env` ni las URL con usuario/clave. Si el fichero se llamó accidentalmente `ede.env`, comprueba cuál usa realmente tu agente antes de renombrarlo y nunca sobrescribas uno existente.

## Paso 5. JSON de cámaras del Mac, orientación y PTZ

Para sustituir temporalmente las cámaras antiguas por las tres Tapo:

```bash
cp config/cameras.tapo3.example.json config/cameras.local.json
```

**Ese `cp` sobrescribe la configuración local si ya existe:** úsalo SOLO cuando hayas decidido sustituirla. Si quieres mantener webcam/Android, **no ejecutes el `cp`**: edita `nano config/cameras.local.json`, conserva las fuentes existentes y añade los objetos `tapo1`, `tapo2` y `tapo3` del ejemplo. Los ID deberán coincidir con el VPS. El archivo local está ignorado por Git; no pongas URLs ni contraseñas literales dentro.

En cada objeto:

- `rotation: 0` por defecto; `90`, `180` o `270` rota en OpenCV antes de la detección/captura. Para una C200C en techo es preferible «Imagen invertida» **en Tapo**, comprobando RTSP; usa `rotation: 180` solo si el flujo sigue invertido. Para Android, modifica exclusivamente su propia `rotation`.
- `ptz.host_env`, `user_env` y `password_env` apuntan a **nombres de variables** del `edge.env`, no a valores secretos. El puerto ONVIF C200C habitual es `2020`.
- `ptz.invert_pan` e `invert_tilt`: pon a `true` únicamente si, al probar las flechas desde MaiaVision, una dirección sale invertida por el montaje o por las convenciones del equipo. Una cámara montada boca abajo NO implica necesariamente invertir ambas tras corregir la imagen desde Tapo.
- En una cámara no motorizada o un Android no pongas `ptz`: sus botones no aparecerán.

Valida sintaxis sin mostrar datos:

```bash
python -m json.tool config/cameras.local.json >/dev/null && echo 'JSON válido'
python - <<'PY'
from pathlib import Path
from apps.edge.agent import load_sources
for source in load_sources(Path('config/cameras.local.json')):
    print(source.camera_id, source.kind, 'rotación', source.rotation, 'PTZ', bool(source.ptz))
PY
```

## Paso 6. Prueba progresiva sin YOLO y luego con YOLO

Asegúrate de no tener otro agente usando el mismo ID/cámara. **En el Mac**, con `edge.env` cargado y el entorno activo:

```bash
python -m apps.edge.agent \
  --config config/cameras.local.json \
  --backend https://maiavision.dbrincau.com \
  --fps 1 --width 640 --no-vision
```

En el dashboard HTTPS, pulsa «Recargar cámaras» si hace falta. Comprueba primero las imágenes y su orientación, después abre una Tapo en vista individual. La sección «Girar cámara» aparecerá **solo si hay vídeo y el hilo ONVIF ha podido inicializar el PTZ y mantiene su sondeo al VPS**. Pulsa una flecha y espera a observar movimiento; las respuestas de API únicamente confirman que el comando está *encolado*. Prueba la parada. Si una flecha va al revés, detén el agente, modifica su `invert_pan`/`invert_tilt` y reinicia. Repite con cada Tapo.

Cuando las tres funcionen, detén el agente con `Ctrl+C` y reactiva detección retirando `--no-vision`:

```bash
python -m apps.edge.agent \
  --config config/cameras.local.json \
  --backend https://maiavision.dbrincau.com \
  --fps 1 --width 640
```

**Recursos:** tres fuentes a 1 FPS son tres análisis secuenciales bajo un bloqueo YOLO compartido; mide CPU/RAM/temperatura del Mac, latencia y WiFi antes de subir a `--fps 2` o `--width 960`. El movimiento PTZ suspende unos segundos los indicadores de perro de esa cámara. La «captura» descarga el último JPEG reducido, no un fichero a máxima resolución original.

Si el Mac tiene un servicio/autoarranque, actualiza su `ExecStart` (Linux systemd) o equivalente (macOS launchd) con la nueva ruta `--config config/cameras.local.json` y el mismo `edge.env`. No ejecutes servicio y comando manual a la vez. El servicio debe cargar variables sin publicarlas en argumentos de proceso. El VPS no ejecuta `apps.edge.agent`.

## Diagnóstico y límites

| Síntoma | Comprobación |
| --- | --- |
| Nueva Tapo no aparece | ID en `MAIA_CAMERAS_JSON` del VPS y en JSON Mac, backend recreado tras cambio de `.env`, URLs reales, agente arrancado. |
| «Sin señal» | La Tapo está enchufada, misma LAN, DHCP/IP reservada, `stream1`/`stream2`, credenciales de cámara, VLC. |
| Imagen invertida | Revisar «Imagen invertida» en Tapo, comprobar RTSP; no aplicar además `rotation:180` si ya viene derecha. |
| Vídeo sí, flechas no aparecen | Instalar `requirements-ptz.txt`, revisar log `Control ONVIF PTZ conectado`, usuario ONVIF/puerto `2020`, actualizar firmware y pulsar «Recargar cámaras». |
| Flechas visibles pero no gira | Probar ONVIF con otro cliente local, verificar función ContinuousMove en perfil, revisar errores PTZ del agente; el HTTP 200 de MaiaVision solo confirma encolado, **no** entrega física. |
| Flechas invertidas | Cambiar `invert_pan` o `invert_tilt` de ESA cámara y reiniciar agente. |
| Error HTTP 401/404 en agente | Token del Mac distinto del VPS o ID no permitido. No imprimir ni compartir secretos. |
| Error 403 PTZ navegador | Sesión/origen HTTPS: entrar por `https://maiavision.dbrincau.com`, no por dominio alternativo ni HTTP. |
| PTZ desaparece tras reinicio de VPS | El agente lo vuelve a anunciar por polling cuando restablece HTTPS y ONVIF. Espera unos segundos y recarga cámaras. |
| Solo se ve la cámara antigua | Tu JSON local fue sustituido: añade las fuentes que deseas mantener; no ejecutan automáticamente todas las cameras del VPS. |

Una limitación importante: **no se ha implementado confirmación de ejecución física, presets, giro mantenido, persecución automática de Maia ni reorientación simultánea coordinada**. Los comandos caducan y las posiciones no se guardan. El cliente `onvif-zeep` necesita validación presencial con la C200C y su firmware. Revisa privacidad doméstica: avisa a cualquier persona que pueda aparecer en vídeo.
