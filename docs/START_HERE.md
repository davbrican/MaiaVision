# Guía inmediata: ejecutar la rama multicámara

Esta funcionalidad se encuentra actualmente en un **pull request sin fusionar**. Si clonas `main` sin cambiar de rama, obtendrás el monitor anterior, NO el dashboard.

```bash
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
git switch feat/web-dashboard-multicamera-android
```

A partir de aquí sigue el [README de esta rama](../README.md). En resumen: crea `.env` desde `.env.example`, genera hash con `python3 scripts/hash_password.py` y dos secretos distintos con `secrets.token_hex(32)`, inicia `docker compose -f infra/docker-compose.yml up -d --build`; abre `http://localhost:8080` y ejecuta el agente en otro terminal con un venv dedicado, `set -a; source .env; set +a` y `python -m apps.edge.agent --config config/cameras.mac.json --backend http://localhost:8080 --no-vision`.

**Android:** lee [android.md](android.md), inicia servidor de IP Webcam en el teléfono y exporta `MAIA_ANDROID_URL` con la URL real de vídeo. Ejecuta el agente usando `config/cameras.android.example.json` y verifica el mosaico. No abras puertos del router de casa ni hagas pública la app Android.

**VPS y Raspberry:** [deployment.md](deployment.md). Para la Pi copia `infra/edge.env.example` como `edge.env` en la raíz y sustituye TODOS los valores. Configura `infra/maia-edge.service.example` con usuario y rutas reales antes de instalar el servicio systemd. No supone que estos equipos ya estén accesibles ni que tres inferencias YOLO rindan correctamente en ARM.
