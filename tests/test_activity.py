"""Tests de actividad: deterministas, sin cámara, red ni modelo YOLO."""

import unittest

from maia_vision.activity import (
    ActivityTracker,
    MOVING,
    NOT_DETECTED,
    NO_REFERENCE,
    STILL,
)


class ActivityTrackerTests(unittest.TestCase):
    def test_starts_without_detection(self):
        tracker = ActivityTracker()
        result = tracker.observe(None, 1.0)
        self.assertEqual(result.status, NOT_DETECTED)
        self.assertIsNone(result.event)
        self.assertIsNone(result.speed_px_s)

    def test_first_detection_is_appearance_without_speed(self):
        tracker = ActivityTracker()
        result = tracker.observe((20, 40), 10.0, 0.92)
        self.assertEqual(result.status, NO_REFERENCE)
        self.assertEqual(result.event, "appearance")
        self.assertIsNone(result.speed_px_s)
        self.assertEqual((result.x, result.y), (20, 40))
        self.assertEqual(result.confidence, 0.92)

    def test_motion_start_and_stop(self):
        tracker = ActivityTracker(movement_threshold=35)
        tracker.observe((0, 0), 0.0)
        still = tracker.observe((10, 0), 1.0)
        self.assertEqual(still.status, STILL)
        self.assertIsNone(still.event)
        moving = tracker.observe((60, 0), 2.0)
        self.assertEqual(moving.status, MOVING)
        self.assertEqual(moving.event, "motion_start")
        self.assertEqual(moving.speed_px_s, 50)
        stopped = tracker.observe((61, 0), 3.0)
        self.assertEqual(stopped.status, STILL)
        self.assertEqual(stopped.event, "motion_stop")

    def test_threshold_is_strictly_greater(self):
        tracker = ActivityTracker(movement_threshold=35)
        tracker.observe((0, 0), 0)
        observation = tracker.observe((35, 0), 1)
        self.assertEqual(observation.status, STILL)

    def test_disappearance_resets_reference(self):
        tracker = ActivityTracker()
        tracker.observe((10, 10), 0)
        gone = tracker.observe(None, 1)
        self.assertEqual(gone.event, "disappearance")
        self.assertEqual(gone.status, NOT_DETECTED)
        self.assertIsNone(tracker.observe(None, 2).event)
        again = tracker.observe((500, 500), 3)
        self.assertEqual(again.event, "appearance")
        self.assertIsNone(again.speed_px_s)
        self.assertEqual(again.status, NO_REFERENCE)

    def test_nonpositive_delta_has_no_division_by_zero(self):
        tracker = ActivityTracker()
        tracker.observe((0, 0), 5)
        observation = tracker.observe((100, 100), 5)
        self.assertEqual(observation.status, NO_REFERENCE)
        self.assertIsNone(observation.speed_px_s)

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            ActivityTracker(movement_threshold=0)


if __name__ == "__main__":
    unittest.main()
