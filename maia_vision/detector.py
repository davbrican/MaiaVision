"""Adaptador YOLO para detectar la clase COCO 'dog' en un fotograma."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


COCO_DOG_CLASS_ID = 16


@dataclass(frozen=True)
class DogDetection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


class DogDetector:
    """Selecciona el perro más confiable; NO reconoce la identidad de Maia."""

    def __init__(self, model_path: str = "yolo26n.pt", confidence: float = 0.45) -> None:
        if not 0.0 < confidence <= 1.0:
            raise ValueError("confidence debe estar en el intervalo (0, 1]")
        # Import diferido: las reglas de actividad y los tests no requieren PyTorch.
        from ultralytics import YOLO

        self._model = YOLO(model_path)
        self._confidence = confidence

    def detect(self, frame: Any) -> DogDetection | None:
        results = self._model.predict(
            frame,
            classes=[COCO_DOG_CLASS_ID],
            conf=self._confidence,
            verbose=False,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return None

        boxes = results[0].boxes
        index = int(boxes.conf.argmax().item())
        coords = [int(value) for value in boxes.xyxy[index].tolist()]
        return DogDetection(*coords, confidence=float(boxes.conf[index].item()))
