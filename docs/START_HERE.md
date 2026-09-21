# Guía inmediata: ejecutar la rama multicámara

Esta funcionalidad se encuentra en un **pull request sin fusionar**. Si clonas `main` sin cambiar de rama, obtendrás el monitor anterior, NO el dashboard.

```bash
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
```

A partir de aquí sigue el [README de esta rama](../README.md). Crea `.env` desde `.env.example`; genera el hash con `python3 scripts/hash_password.py` y dos secretos distintos con `secrets.token_hex(32)`. Para producción configura `MAIA_PUBLIC_ORIGIN=https://maiavision.dbrincau.com` y `MAIA_COOKIE_SECURE=true`. Inicia:

```bash
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://127.0.0.1:8102/api/health
```

En desarrollo local abre `http://localhost:8102` y ejecuta el agente en otra terminal con venv dedicado:

```bash
set -a; source .env; set +a
python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8102 --no-vision
```

**VPS con Nginx existente:** apunta `maiavision.dbrincau.com` mediante HTTPS a `http://127.0.0.1:8102`. NO cambies tu configuración de los demás sitios. El backend `8000` está aislado dentro de Docker. Valida disponibilidad de 8102 en el host con `sudo ss -ltnp | grep ':8102 '`. El puerto de la app Android puede seguir siendo 8080 en la red local: no es el puerto 8102 del VPS.

**Android:** lee [android.md](android.md), inicia servidor IP Webcam en el teléfono y exporta `MAIA_ANDROID_URL` con la URL real de vídeo. Ejecuta el agente con `config/cameras.android.example.json` y verifica el mosaico. No abras puertos del router ni hagas pública la cámara Android.

**VPS y Raspberry:** consulta [deployment.md](deployment.md). Para Pi copia `infra/edge.env.example` como `edge.env` en la raíz y sustituye todos los valores. Configura `infra/maia-edge.service.example` con usuario y rutas reales antes de instalar el servicio systemd. La prueba con tres cámaras y YOLO en ARM sigue pendiente.
