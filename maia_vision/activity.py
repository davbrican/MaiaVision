"""Reglas puras para estados y eventos de movimiento aparente.

No identifica animales ni infiere sueño, ansiedad o velocidad física.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


NOT_DETECTED = "NO DETECTADA"
NO_REFERENCE = "SIN REFERENCIA"
STILL = "QUIETA"
MOVING = "MOVIMIENTO"


@dataclass(frozen=True)
class Observation:
    """Resultado observado para un fotograma procesado."""

    status: str
    x: int | None = None
    y: int | None = None
    confidence: float | None = None
    speed_px_s: float | None = None
    event: str | None = None


class ActivityTracker:
    """Compara centros de cajas entre fotogramas utilizando tiempo monotónico.

    Los eventos representan cambios aparentes; una pérdida de detección elimina
    la referencia previa para evitar saltos artificiales en la reaparición.
    """

    def __init__(self, movement_threshold: float = 35.0) -> None:
        if movement_threshold <= 0:
            raise ValueError("movement_threshold debe ser mayor que cero")
        self.movement_threshold = movement_threshold
        self._position: tuple[int, int] | None = None
        self._time: float | None = None
        self._status = NOT_DETECTED

    def observe(
        self,
        position: tuple[int, int] | None,
        now: float,
        confidence: float | None = None,
    ) -> Observation:
        """Procesa una observación; `now` debe proceder de time.monotonic()."""
        previous_status = self._status

        if position is None:
            self._position = None
            self._time = None
            self._status = NOT_DETECTED
            return Observation(
                status=NOT_DETECTED,
                event="disappearance" if previous_status != NOT_DETECTED else None,
            )

        x, y = position
        speed: float | None = None
        status = NO_REFERENCE

        if self._position is not None and self._time is not None:
            delta_t = now - self._time
            if delta_t > 0:
                speed = hypot(x - self._position[0], y - self._position[1]) / delta_t
                status = MOVING if speed > self.movement_threshold else STILL

        self._position = position
        self._time = now
        self._status = status

        event = None
        if previous_status == NOT_DETECTED:
            event = "appearance"
        elif status == MOVING and previous_status != MOVING:
            event = "motion_start"
        elif previous_status == MOVING and status == STILL:
            event = "motion_stop"

        return Observation(
            status=status,
            x=x,
            y=y,
            confidence=confidence,
            speed_px_s=speed,
            event=event,
        )
