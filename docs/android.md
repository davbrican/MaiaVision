# Usar un móvil Android como cámara WiFi

Puedes utilizar un Android antiguo como cámara secundaria. Una opción es [IP Webcam para Android](https://play.google.com/store/apps/details?id=com.pas.webcam), que ofrece vídeo MJPEG por WiFi. Sirve cualquier app que exponga una URL MJPEG HTTP o RTSP compatible con OpenCV.

## Pasos

1. Conecta Android y Mac/Raspberry a la **misma red WiFi**. Instala IP Webcam, concede permiso de cámara e inicia el servidor. Evita que el ahorro de batería cierre la aplicación y vigila temperatura y alimentación.
2. La aplicación mostrará una URL local, por ejemplo `http://192.168.1.50:8080`. **Ese 8080 es el puerto local del móvil y puede mantenerse así: NO es el puerto del VPS**, que ahora es `8102` y sólo escucha en localhost. Abre la URL del móvil desde el Mac y encuentra la ruta real de vídeo, normalmente `/video` o `/videofeed` según aplicación/versión.
3. Comprueba que se ve el flujo MJPEG o RTSP, no solamente la página HTML de IP Webcam. Reserva una IP local en DHCP para evitar cambios.
4. En el Mac, dentro del entorno Edge, establece variables privadas (sin publicarlas):

```bash
export MAIA_EDGE_TOKEN='EL_MISMO_TOKEN_PRIVADO_DEL_VPS'
export MAIA_ANDROID_URL='http://IP_REAL_DEL_MOVIL:PUERTO/RUTA_REAL'
python -m apps.edge.agent --config config/cameras.android.example.json --backend https://maiavision.dbrincau.com --fps 2 --no-vision
```

5. Accede al dashboard por `https://maiavision.dbrincau.com`, confirma que aparecen `webcam` y `android` y quita `--no-vision` para activar YOLO. Esos dos IDs deben estar permitidos en `MAIA_CAMERAS_JSON` del `.env` del VPS.

Para **desarrollo completo en el mismo Mac**, puedes usar `--backend http://localhost:8102` siempre que Docker esté arrancado allí y su `.env` tenga `MAIA_PUBLIC_ORIGIN=http://localhost:8102` y `MAIA_COOKIE_SECURE=false`. Para un Mac que apunte al VPS usa siempre el dominio HTTPS, no `localhost:8102`.

## Seguridad y problemas frecuentes

- No abras puertos HTTP/RTSP en el router: Android→Mac/Raspberry ocurre dentro de la LAN y Mac/Raspberry→VPS usa HTTPS. Configura autenticación local de IP Webcam si está disponible y evita integraciones cloud que no necesites.
- Si no conecta: comprueba IP y ruta real del vídeo, la misma WiFi (sin aislamiento de invitados), y que IP Webcam siga encendida. No compartas URLs con credenciales.
- Si se interrumpe: reduce FPS y resolución, revisa el ahorro de batería y la temperatura; no desactives salvaguardas térmicas.
- La vista remota actual usa JPEG/MJPEG a pocos FPS, no streaming HD/30 FPS. No se graba audio ni vídeo en el VPS; se guardan eventos de texto y el último frame se mantiene temporalmente en RAM.
