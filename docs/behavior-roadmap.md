# Evolución del análisis de Maia — qué mide y qué NO

## Versión actual (implementada en la rama de la PR #1)

- Web privada: `https://maiavision.dbrincau.com`, sin ruta adicional `/dashboard`.
- Detección de la categoría **perro** con YOLO COCO, no identificación biométrica de Maia. Si aparece otro perro, el detector puede confundirlo.
- Estado visual por cámara: `NO DETECTADA`, `SIN REFERENCIA`, `QUIETA`, `MOVIMIENTO`; transiciones de aparición, pérdida de detección, inicio y fin de movimiento.
- Nueva tarjeta **última detección**: cámara y hora del último fotograma muestreado con un perro visible en los últimos siete días. No puede saber que Maia está en una zona ciega o deducir el camino de una cámara a otra. Cuando varias cámaras se solapan, la última que envía muestra no representa un desplazamiento real.
- Nueva tarjeta **actividad observada**, por cámara y para 1 h / 4 h / 24 h: porcentaje de muestras `MOVIMIENTO` entre muestras evaluables `QUIETA` y `MOVIMIENTO`, cada ~10 s. No son minutos de ejercicio, velocidad, pasos, kilómetros ni un diagnóstico. No sumar porcentajes de cámaras distintas. Mostrar número de muestras y `Sin datos` cuando no hay observaciones válidas.
- Solo se guardan metadatos de estado en `activity_samples` (SQLite, 7 días), no fotogramas/vídeos. El historial empieza tras desplegar esta versión. Endpoint privado `GET /api/insights?window_minutes=60` requiere inicio de sesión; con `--no-vision` no se registran observaciones de perro.

## Ideas de evolución en fases verificables

| Conducta solicitada | Qué se puede observar | Qué hace falta antes de activarlo |
| --- | --- | --- |
| Actividad diaria | Muestreo de movimiento por cámara, cambios y periodos sin detección | Ajustar umbral de desplazamiento y normalizar por ancho del perro/escala, validar con clips reales y advertir zonas ciegas. Un collar acelerómetro puede contrastar el movimiento real. |
| Última zona vista | Última cámara que detectó un perro y hora | Fijar zonas y coberturas, sincronizar relojes, opcional reidentificación calibrada. No deducir trayectorias ni afirmar posición en un recoveco. |
| Visitas al bebedero | Perro dentro de zona de agua durante varios segundos | Definir ROI para bebedero, detectar cabeza/hocico + postura/duración, comprobar falsos positivos (olfatear ≠ beber). Sensor de peso/caudal para confirmar agua consumida. |
| Juego con peluche | Contacto y desplazamiento simultáneo de perro y objeto | Dataset real del peluche específico, detección/seguimiento de objetos, definición de episodio y clips anotados para evaluar falsos positivos. |
| Coger/morder objetos | Interacción boca-objeto sostenida durante varios fotogramas | Modelo para hocico y objetos relevantes, cámara con visibilidad, dataset etiquetado por acción, umbral temporal y revisión humana. Con JPEG a ~2 FPS no prometer aviso de peligro inmediato. |
| Aburrimiento/felicidad | Conductas concretas observables (juego, descanso, exploración, repetición, interacción) | No etiquetar estados internos automáticamente. Se requieren evaluación contextual, observadores y medidas de bienestar validadas. No deducir aburrimiento de quietud ni felicidad de mover la cola. |

### Criterios de aceptación de módulos futuros

1. Usuario marca en cada cámara zonas privadas y zona del bebedero/juguete; nada se envía a servicios de IA externos por defecto.
2. Recopilación de clips para entrenamiento **solo con consentimiento explícito**, almacenamiento local cifrado y política de borrado. No guardar vídeo incidental en el VPS actual.
3. Definir eventos medibles en términos observables antes de entrenar. Dataset propio de diferentes ángulos, iluminación, perros/objetos y oclusiones; separar entrenamiento y test por sesión.
4. Medir precisión, recall y falsas alarmas por hora frente a anotación manual. Rechazar una función si no supera criterios definidos antes de pruebas reales.
5. Añadir eventos al backend autenticado con etiqueta, confianza, método y fuente. No convertir una probabilidad de clase visual en un diagnóstico veterinario.
6. Si se incorpora otra IA/VLM, primero revisión de privacidad, coste, licencias, latencia y posibilidad de funcionamiento totalmente local.

**Literatura para contextualizar (no implica que MaiaVision ya logre esos resultados):** revisión sistemática de indicadores de bienestar canino, Journal of Veterinary Behavior 2024, DOI `10.1016/j.jveb.2023.12.007`; estudio 2026 de pipeline visual canino en condiciones controladas, DOI `10.3389/ftox.2026.1758963`, que entrenó modelos específicos y muestra diferencias importantes de exactitud entre clases. Resultados de estudios especializados NO se extrapolan directamente a una webcam doméstica con YOLO genérico.
