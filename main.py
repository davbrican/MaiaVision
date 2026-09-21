"""CLI de MaiaVision: webcam, detección, actividad y registro CSV local."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from maia_vision.activity import ActivityTracker, Observation


FIELDS = ("timestamp", "event", "status", "x", "y", "confidence", "speed_px_s")


def positive_float(value: str) -> float:
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("debe ser un número finito mayor que 0")
    return number


def confidence_float(value: str) -> float:
    number = float(value)
    if not 0 < number <= 1:
        raise argparse.ArgumentTypeError("debe estar entre 0 (excluido) y 1")
    return number


def camera_index(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("debe ser un índice de cámara >= 0")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MaiaVision: monitor local de mascotas")
    parser.add_argument("--camera", type=camera_index, default=0, help="índice de webcam (0)")
    parser.add_argument("--model", default="yolo26n.pt", help="pesos del detector")
    parser.add_argument("--confidence", type=confidence_float, default=0.45)
    parser.add_argument("--movement-threshold", type=positive_float, default=35.0,
                        help="umbral de movimiento aparente en píxeles/s (35)")
    parser.add_argument("--log-interval", type=positive_float, default=2.0,
                        help="intervalo de muestras CSV en segundos (2)")
    parser.add_argument("--output", type=Path, default=Path("data/activity.csv"))
    return parser.parse_args()


def csv_row(observation: Observation, event: str) -> dict[str, object]:
    """Serializa una observación sin inventar coordenadas o velocidad ausentes."""
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": event,
        "status": observation.status,
        "x": observation.x if observation.x is not None else "",
        "y": observation.y if observation.y is not None else "",
        "confidence": round(observation.confidence, 4) if observation.confidence is not None else "",
        "speed_px_s": round(observation.speed_px_s, 2) if observation.speed_px_s is not None else "",
    }


def run(args: argparse.Namespace) -> int:
    # Dependencias de cámara/ML diferidas: tests de actividad ejecutables offline.
    import cv2
    from maia_vision.detector import DogDetector

    print("Cargando detector. La primera ejecución puede descargar los pesos del modelo...")
    detector = DogDetector(model_path=args.model, confidence=args.confidence)
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(
            f"No se pudo abrir la cámara {args.camera}. Revisa el índice, los permisos "
            "de cámara y si otra aplicación la está utilizando."
        )

    tracker = ActivityTracker(movement_threshold=args.movement_threshold)
    trajectory: deque[tuple[int, int]] = deque(maxlen=32)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not args.output.exists() or args.output.stat().st_size == 0
    last_sample: float | None = None

    print(f"Cámara {args.camera} activa. Pulsa Q para salir. CSV: {args.output}")
    try:
        with args.output.open("a", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            if needs_header:
                writer.writeheader()
                output.flush()

            try:
                while True:
                    ok, frame = camera.read()
                    if not ok:
                        print("La webcam ha dejado de entregar fotogramas.", file=sys.stderr)
                        break

                    detection = detector.detect(frame)
                    now = time.monotonic()
                    if detection is None:
                        trajectory.clear()
                        observation = tracker.observe(None, now)
                    else:
                        observation = tracker.observe(
                            detection.center, now, detection.confidence
                        )
                        trajectory.append(detection.center)
                        cv2.rectangle(frame, (detection.x1, detection.y1),
                                      (detection.x2, detection.y2), (0, 255, 0), 2)
                        cv2.circle(frame, detection.center, 4, (0, 200, 255), -1)
                        cv2.putText(frame, f"PERRO {detection.confidence:.2f}",
                                    (detection.x1, max(detection.y1 - 10, 20)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

                    for first, second in zip(trajectory, list(trajectory)[1:]):
                        cv2.line(frame, first, second, (0, 200, 255), 2)
                    cv2.putText(frame, f"Estado: {observation.status}", (15, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                    wrote = False
                    if observation.event is not None:
                        writer.writerow(csv_row(observation, observation.event))
                        wrote = True
                    if last_sample is None or now - last_sample >= args.log_interval:
                        writer.writerow(csv_row(observation, "sample"))
                        last_sample = now
                        wrote = True
                    if wrote:
                        output.flush()

                    cv2.imshow("MaiaVision - Q para salir", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            except KeyboardInterrupt:
                print("Monitor detenido por el usuario.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
