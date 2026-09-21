# AGENTS.md — Guía operativa de MaiaVision

## 0. Propósito y contexto

MaiaVision es un proyecto personal de monitorización de mascotas mediante visión artificial. Su primera usuaria es Maia, aunque el modelo preentrenado reconoce **perros en general**. Se ejecuta **localmente en el ordenador** con webcam: Python + OpenCV + Ultralytics YOLO26. No guarda vídeo por defecto, no necesita API de pago y no tiene relación con ningún proyecto de semáforos.

El objetivo final es consultar actividad y eventos desde un dashboard, con un recorrido gradual y verificable. La prioridad es que **cada fase funcione antes de incorporar la siguiente**, con separación entre lo implementado y lo previsto. Ver README.md para instrucciones ejecutables.

## 1. Contrato del MVP (implementado en código)

- CLI `python main.py` con `--camera`, `--model`, `--confidence`, `--movement-threshold`, `--log-interval`, `--output`; salida con Q o Ctrl+C.
- Captura local con OpenCV; inferencia YOLO26n `yolo26n.pt`, filtro clase COCO 16 (`dog`), confianza configurable.
- Se elige la detección de perro de mayor confianza; **no hay reidentificación, multi-tracking ni garantía de que sea Maia**.
- Caja delimitadora, punto central, trayectoria reciente; velocidad aparente estimada en píxeles/segundo usando reloj monotónico entre fotogramas procesados.
- Estados de observación: `NO DETECTADA`, `SIN REFERENCIA`, `QUIETA`, `MOVIMIENTO`. Eventos `appearance`, `disappearance`, `motion_start`, `motion_stop`, más `sample` periódico.
- Registro CSV con cabecera `timestamp,event,status,x,y,confidence,speed_px_s` en `data/activity.csv`, local y append. `data/` excluido del control de versiones.
- Pruebas unitarias de la lógica de actividad sin abrir cámara ni descargar modelos.

El MVP **no** identifica posturas, sueño, emociones, ansiedad, ladridos, entradas/salidas reales de una habitación o velocidad métrica. No incluye todavía zonas, SQLite, audio, imágenes, API, React, alertas, cloud ni cámaras IP. No describir estas capacidades como terminadas.

## 2. Arquitectura y responsabilidades

```text
webcam → OpenCV (main.py) → DogDetector (maia_vision/detector.py)
                                   ↓ detección / centro / confianza
                            ActivityTracker (maia_vision/activity.py)
                                   ↓ estados + eventos
                         ventana local + CSV local
```

- `main.py`: CLI, validación, captura, gestión de recursos, rendering y persistencia CSV. Mantenerlo como orquestador, no enterrar reglas de dominio en el bucle.
- `maia_vision/detector.py`: adaptador de inferencia; aislar Ultralytics para poder intercambiar modelos o simular detecciones. Importar librerías costosas al inicializar detector para permitir tests de lógica sin ellas.
- `maia_vision/activity.py`: lógica pura/dependencias estándar; diferenciar observación, inferencia heurística y evento; estados definidos de forma estable.
- `tests/`: `unittest` con casos controlados para umbrales, aparición, desaparición y transiciones; no depender de hardware ni red.
- `.github/workflows/ci.yml`: comprobar sintaxis y pruebas puras. No presentarlo como prueba de inferencia o compatibilidad con webcams.

## 3. Reglas técnicas para agentes y colaboradores

1. **Inspecciona primero el código, README y este AGENTS.md.** No reescribas arquitectura a ciegas ni mezcles un proyecto diferente.
2. Trabaja en ramas de feature; mantén cambios pequeños y revisables. No mezclar directo a `main` sin la aprobación que corresponda al equipo; solicita revisión al integrar cambios posteriores. Esta inicialización es el bootstrap expresamente solicitado.
3. Python 3.11+ recomendado; tipado y docstrings para funciones no triviales; preferir biblioteca estándar para reglas y persistencia simple. Evitar introducir Docker, Redis, PostgreSQL, servidores o frontend hasta la fase que los requiera.
4. No incorporar claves, imágenes domésticas, pesos de modelos, registros, vídeos, archivos `.env`, entornos virtuales ni datos personales al repositorio.
5. Para cada cambio de actividad/detección añade tests reproducibles y documenta falsos positivos, unidades, umbrales y supuestos. Ejecuta `python -m unittest discover -s tests -v` y `python -m compileall -q main.py maia_vision tests`.
6. No llamar a una heurística «IA que diagnostica ansiedad». `NO DETECTADA` no es «fuera de la habitación»; `QUIETA` no es «durmiendo»; los píxeles/segundo no son m/s.
7. Cámaras fijas y un perro visible son hipótesis de fase 1. Contemplar oclusiones, detecciones intermitentes y varios perros como limitaciones; no atribuir identidad sin sistema específico.
8. Cerrar cámara, ficheros y ventanas en `finally`; errores útiles cuando no hay acceso a cámara. No cambiar a `opencv-python-headless` si se requiere ventana local.
9. Interfaz inicial en español; nombres de módulos, claves CSV y eventos estables en inglés por compatibilidad. Documentación de usuario en español.
10. No añadir streaming ni exposición de cámara por red sin autenticación, cifrado, permisos, controles de acceso y una política de retención documentada.

## 4. Roadmap y criterios de aceptación

### Fase 1: monitor local (código inicial incluido)

- Webcam real muestra vídeo y detecta un perro con caja correcta (validación manual pendiente en equipo del usuario).
- Cambios del centro de caja generan estados y eventos aproximados; sin detección se reinicia referencia; no se mide movimiento físico real.
- CSV se crea y escribe cada `--log-interval` segundos además de transiciones, sin grabar imagen ni audio.
- CLI --help, cierre con Q, ejecución de pruebas puras y ausencia de secretos.

### Fase 2: historial y analítica (pendiente)

- Repositorio SQLite, sesiones, eventos, porcentajes de tiempo visible y movimiento observado, gráficos horarios, exportación.
- Métricas distinguen claramente «no observado» de «reposo»; datos retenidos según configuración.
- Pruebas de migración y cálculo de métricas con registros sintéticos.

### Fase 3: zonas de interés (pendiente)

- Dibujar/editar polígonos cama, sofá, puerta sobre vista fija y persistir sus coordenadas normalizadas por cámara.
- Generar eventos de entrada/salida de **zona visible** con histéresis y tolerancia a pérdidas breves; no confundir con salida real de la habitación.
- Pruebas geométricas de fronteras, redimensionado y oclusiones.

### Fase 4: comportamiento observable + audio (pendiente)

- Actividad repetitiva y periodos largos con reglas configurables y ventanas temporales. No atribuir diagnóstico de salud/estrés.
- Detección de posibles ladridos requiere micrófono y clasificador de audio independiente; registrar incertidumbre y falsos positivos; opt-in para audio.

### Fase 5: aplicación web y alertas (pendiente)

- FastAPI para histórico y configuración, React + TypeScript responsive para vista en directo, sesiones, gráficas y eventos.
- Streaming en red solo tras autenticación, TLS y autorización; alertas configurables, evitando notificaciones excesivas.
- La funcionalidad local debe seguir funcionando sin backend remoto.

### Fase 6: robustez (pendiente)

- Multi-perro y tracking de identidad **evaluados** antes de asignar eventos a Maia; calibración sobre escenas reales, benchmark de FPS/uso de CPU y falsos positivos; tests de integración con vídeos de prueba no personales.

## 5. Privacidad, modelo y licencias

Procesamiento de fotogramas local por defecto. Una conexión puede usarse en instalación y primera descarga de `yolo26n.pt`; no afirmar funcionamiento 100 % sin red antes de disponer de pesos. Para futura publicación/comercialización revisar licencias de Ultralytics, pesos y resto de dependencias; Ultralytics publica opciones AGPL-3.0/Enterprise: https://www.ultralytics.com/license. No otorgar automáticamente al código propio una licencia sin decisión del propietario.

## 6. Definición de terminado

Una tarea termina cuando: implementación coherente con el alcance, tests pertinentes aprobados, documentación CLI/arquitectura actualizada, riesgos y limitaciones explicitados, privacidad respetada y diferencias entre simulación y prueba real declaradas. Si no se puede probar con cámara en el entorno de trabajo, indicar explícitamente «pendiente de validación con webcam real».
