# Usar un móvil Android como cámara WiFi

Sí. Puedes utilizar un Android antiguo como cámara secundaria sin comprar hardware. Una opción es [IP Webcam para Android](https://play.google.com/store/apps/details?id=com.pas.webcam), que permite publicar MJPEG por WiFi y funcionar sin Internet para el flujo local; comprueba la versión, permisos y opciones disponibles en tu teléfono. No dependemos de esa aplicación: sirve cualquier app que exponga una URL de vídeo **real** compatible con OpenCV (MJPEG HTTP o RTSP).

## Pasos

1. Conecta Android y Mac/Raspberry a **la misma red WiFi**. Instala IP Webcam en Android; da permiso de cámara y pulsa «Iniciar servidor» (la etiqueta puede variar por versión). Deja pantalla/servicio activo y desactiva optimización agresiva de batería de esa app si se interrumpe. Vigila calor, alimentación y autonomía; no dejes un teléfono sobrecalentándose conectado constantemente.
2. La aplicación mostrará una URL local tipo `http://192.168.1.50:8080`. Ábrela desde el ordenador para confirmar conexión. Identifica la ruta exacta del stream MJPEG desde la interfaz; en versiones habituales suele ser `/video` o `/videofeed`, pero **no asumas cuál sin comprobarlo**. No copies la URL del panel HTML como si fuera un stream de fotogramas.
3. Para pruebas puedes inspeccionar el vídeo con VLC o un pequeño script OpenCV, preferiblemente con autenticación local de la app cuando la permita. Establece una reserva DHCP para que no cambie la IP; evita publicar la app por Internet, desactiva integraciones cloud del proveedor que no uses y no grabes audio si no está justificado.
4. En terminal, con el entorno del Edge Agent activo, establece la URL como variable PRIVADA: `export MAIA_ANDROID_URL='http://IP_REAL:PUERTO/RUTA_REAL'`. Si la URL contiene credenciales, nunca la pegues en chats, capturas, comandos compartidos ni repositorio.
5. Desde la raíz del repositorio y con `MAIA_EDGE_TOKEN` exportado, ejecuta `python -m apps.edge.agent --config config/cameras.android.example.json --backend http://localhost:8080 --no-vision`. Abre `http://localhost:8080` desde el Mac para ver webcam y Android. El backend debe tener registrados los IDs `webcam` y `android` en `MAIA_CAMERAS_JSON`.
6. Cuando funcione, quita `--no-vision` para habilitar YOLO. El mismo `source_env` será compatible con un flujo RTSP de otra app/cámara sin cambiar el motor.

## Seguridad y privacidad

Las conexiones Android→agente quedan en la LAN; si la aplicación solo ofrece HTTP, no viajes con ella a Internet ni abras puertos del router. Usa autenticación de la cámara si está disponible; WiFi WPA2/WPA3, red privada y, si es posible, VLAN de IoT. Edge→VPS debe usar **HTTPS**. Crea una contraseña potente para la web, no compartas tokens y considera si otras personas pueden aparecer en las cámaras. La web no guarda vídeo; se envían fotogramas al VPS para ofrecer la visualización autenticada. Si alguna app incluye nube propia, revisa/deshabilita esa opción según tus preferencias.

## Problemas frecuentes

- No abre: verifica que ambos estén en la misma subred, el modo aislado de invitados esté desactivado, la app siga encendida y has elegido la URL de vídeo, no solo la portada web.
- Se corta: Android puede cerrar la app al bloquear pantalla o por ahorro de batería; ajusta configuración del sistema y baja resolución/FPS. No suprimas salvaguardas térmicas.
- Retraso: MJPEG consume ancho de banda y el agente muestrea por defecto 2 FPS; no esperes vídeo 30 FPS. Reduce `--width` y prueba `--fps 1` con una Raspberry.
- No aparece en el dashboard: revisa el ID `android` registrado en `.env` y los mensajes del agente sin publicar logs que contengan URL/credenciales.
