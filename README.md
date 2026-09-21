# 🐾 MaiaVision — Smart Pet Monitoring

Monitor local de mascotas con **Python, OpenCV y detección de objetos mediante YOLO**. El proyecto nace para observar a Maia con una webcam, registrar actividad y construir gradualmente un panel de seguimiento. **No es el proyecto de semáforos.**

> **Estado:** MVP local. Funciona con una cámara, detecta la clase `dog`, estima movimiento aparente en píxeles/segundo, dibuja la detección y la trayectoria reciente, y guarda eventos y muestras en CSV. Las zonas, el audio, las alertas, SQLite y el dashboard web son fases futuras; **no están implementados**.

## Qué hace hoy

- Abre la webcam del ordenador (por defecto, índice `0`) y muestra vídeo en una ventana de OpenCV.
- Carga `yolo26n.pt` de Ultralytics y filtra detecciones de perro (clase COCO `16`). La primera ejecución puede descargar los pesos y requiere conexión.
- Cuando aparecen varios perros, selecciona **la detección con mayor confianza**: el MVP **no identifica individualmente a Maia** ni sigue identidades entre animales.
- Dibuja una caja, el centro y una trayectoria reciente. Estima el movimiento aparente con diferencias entre centros y tiempo monotónico.
- Distingue `NO DETECTADA`, `SIN REFERENCIA`, `QUIETA` y `MOVIMIENTO`; registra apariciones, desapariciones, inicios/finales de movimiento y muestras periódicas.
- Guarda únicamente un **CSV local** por defecto: **no graba ni sube vídeo, audio o imágenes**.

## Requisitos

- Python 3.11+ recomendado, macOS/Windows/Linux, webcam y permisos de cámara.
- Entorno con interfaz gráfica para `cv2.imshow`; no está pensado para un servidor headless.
- Dependencias: `opencv-python` y `ultralytics` (este último instalará sus dependencias, incluido PyTorch).
- En macOS: concede permiso de cámara a Terminal/iTerm/tu IDE en Ajustes del sistema → Privacidad y seguridad → Cámara. En algunos equipos otra aplicación puede estar ocupando la webcam.

## Instalación

```bash
git clone https://github.com/davbrican/MaiaVision.git
cd MaiaVision
python3 -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Si tienes varias cámaras o quieres ajustar la sensibilidad:

```bash
python main.py --camera 1 --confidence 0.50 --movement-threshold 55 --log-interval 2
python main.py --help
```

Pulsa **Q** en la ventana para salir, o `Ctrl+C` en la terminal. Los datos se guardan en `data/activity.csv` (ruta configurable con `--output`). Ejecuta desde la raíz del proyecto. Si `python` no existe en macOS, prueba `python3` dentro del entorno virtual.

## Parámetros

| Argumento | Por defecto | Significado |
| --- | --- | --- |
| `--camera` | `0` | Índice de la webcam local. |
| `--model` | `yolo26n.pt` | Pesos del modelo YOLO de detección. |
| `--confidence` | `0.45` | Umbral de confianza (`0` a `1`). |
| `--movement-threshold` | `35` | Umbral **aparente** en píxeles/segundo. |
| `--log-interval` | `2` | Segundos entre muestras periódicas, además de eventos. |
| `--output` | `data/activity.csv` | CSV local; se añade al existente y se crea cabecera si es necesario. |

### Esquema del registro

`timestamp,event,status,x,y,confidence,speed_px_s`.

- `timestamp`: fecha/hora local con zona horaria.
- `event`: `appearance`, `disappearance`, `motion_start`, `motion_stop` o `sample`.
- `status`: estado estimado de la detección seleccionada.
- `x,y`: centro del rectángulo en píxeles; vacíos si no hay detección.
- `confidence`: confianza de la detección; vacía si no hay detección.
- `speed_px_s`: velocidad aparente del centro, vacía si no existe referencia previa.

El movimiento se calcula entre **fotogramas procesados**, no es una velocidad real en m/s ni mide movimiento de extremidades. Una cámara móvil, cambios del rectángulo, oclusiones y errores de detección pueden producir falsos eventos. `QUIETA` significa solamente «el centro de la caja cambia poco», **no equivale a dormir**. `NO DETECTADA` significa «no vista por el detector», **no que haya salido de la habitación**. Sin identificación individual, no atribuir datos a Maia si entra otro perro.

## Arquitectura del MVP

```text
Webcam local
    │ fotogramas
    ▼
OpenCV ──► DogDetector (Ultralytics YOLO; clase dog)
                           │ caja / confianza / centro
                           ▼
                  ActivityTracker (reglas puras)
                           │ estado + evento
              ┌────────────┴───────────┐
              ▼                        ▼
       Ventana OpenCV             CSV local
       + trayectoria          data/activity.csv
```

```text
MaiaVision/
├── README.md
├── AGENTS.md
├── main.py                  # CLI y ciclo de captura
├── maia_vision/
│   ├── __init__.py
│   ├── activity.py          # Estado, velocidad y eventos; sin dependencias externas
│   └── detector.py          # Adaptador YOLO para perros
├── tests/
│   └── test_activity.py     # Unit tests sin cámara ni modelo
├── requirements.txt
├── .gitignore
└── .github/workflows/ci.yml
```

El ciclo de cámara e inferencia se ejecuta de forma local y síncrona; no hay API ni transmisión remota. Para pruebas unitarias:

```bash
python -m unittest discover -s tests -v
```

## Roadmap — no confundir con funciones entregadas

| Fase | Objetivo | Estado |
| --- | --- | --- |
| 1 · MVP | Detección, recuadro, trayectoria, estado aparente y CSV | Implementado en código; pendiente de probar con la cámara real del usuario. |
| 2 · Historial | SQLite, sesiones, métricas horarias, exportación y retención configurable | Pendiente |
| 3 · Zonas | Definir polígonos en la imagen (cama, sofá, puerta); detectar entrada/salida con histéresis | Pendiente |
| 4 · Comportamiento observable | Patrones de deambulación, inactividad prolongada y ladridos **con micrófono y clasificador de audio** | Pendiente |
| 5 · Dashboard | FastAPI + React: cámara, eventos, estadísticas, configuración y alertas explícitas | Pendiente |
| 6 · Robustez | Identidad multi-perro, modelos/umbrales calibrados, configuración y despliegue seguro | Pendiente |

**Criterios para evolucionar:** métricas con ventanas temporales e histéresis, calibración con vídeos reales y pruebas contra oclusiones; evaluación de falsos positivos antes de activar alertas. No diagnosticar estrés, ansiedad, salud o emociones a partir de cajas de detección. Las futuras notificaciones deben ser configurables y respetar privacidad.

## Privacidad y seguridad

- Procesamiento local. `data/`, pesos del modelo, entornos virtuales y archivos de vídeo están ignorados por Git. No incluyas imágenes de la casa, credenciales, tokens ni registros personales en commits.
- La **descarga inicial del modelo y la instalación** sí se comunican con proveedores externos; la aplicación no envía deliberadamente los fotogramas a ningún servicio.
- Cuando se añada acceso remoto, requerirá autenticación, transporte cifrado y consentimiento de las personas que puedan aparecer en cámara. Evitar grabación permanente por defecto y aplicar política de retención.
- Se deben revisar las condiciones de licencia de **Ultralytics** (AGPL-3.0 o licencia Enterprise según modalidad) antes de redistribuir o comercializar un producto integrado: https://www.ultralytics.com/license.

## Fuentes técnicas

- [Ultralytics — instalación](https://docs.ultralytics.com/quickstart/).
- [Ultralytics — YOLO26](https://docs.ultralytics.com/models/yolo26/).
- [Ultralytics — resultados de detección](https://docs.ultralytics.com/tasks/detect/).
- [OpenCV — documentación](https://docs.opencv.org/).

Consulta [`AGENTS.md`](AGENTS.md) para el contexto completo, estándares de contribución y criterios de aceptación para agentes y colaboradores.
