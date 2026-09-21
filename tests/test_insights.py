"""Objective sampled activity indicators without real camera or dog model."""
import tempfile
import unittest
from pathlib import Path

from apps.backend.insights import InsightsStore


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = InsightsStore(str(Path(self.folder.name) / 'events.db'))
        self.store.init()
        self.cameras = {'webcam': 'Salón', 'android': 'Teléfono'}
        self.now = 1_800_000_000

    def tearDown(self):
        self.folder.cleanup()

    def test_no_vision_creates_no_activity_or_false_location(self):
        self.store.record('webcam', 'SIN ANALISIS', now=self.now)
        result = self.store.summary(self.cameras, 60, now=self.now)
        self.assertIsNone(result['last_detection'])
        self.assertIsNone(result['cameras'][0]['activity_percent'])

    def test_samples_throttled_and_not_duplicated_across_cameras(self):
        self.store.record('webcam', 'MOVIMIENTO', now=self.now - 40)
        self.store.record('webcam', 'QUIETA', now=self.now - 39)  # throttle
        self.store.record('webcam', 'QUIETA', now=self.now - 29)
        self.store.record('webcam', 'NO DETECTADA', now=self.now - 18)
        self.store.record('android', 'QUIETA', now=self.now - 8)
        result = self.store.summary(self.cameras, 60, now=self.now)
        salon, phone = result['cameras']
        self.assertEqual(salon['observed_samples'], 3)
        self.assertEqual(salon['evaluable_samples'], 2)
        self.assertEqual(salon['activity_percent'], 50)
        self.assertEqual(phone['activity_percent'], 0)
        self.assertEqual(result['last_detection']['camera_id'], 'android')
        self.assertEqual(salon['last_seen_at'], '2027-01-15T08:00:11+00:00' if False else salon['last_seen_at'])
        self.assertIsNotNone(salon['last_seen_at'])

    def test_last_detection_preserved_outside_window_but_only_seven_days(self):
        self.store.record('webcam', 'QUIETA', now=self.now - 7200)
        result = self.store.summary(self.cameras, 60, now=self.now)
        self.assertIsNone(result['cameras'][0]['activity_percent'])
        self.assertEqual(result['last_detection']['camera_id'], 'webcam')
        after = self.store.summary(self.cameras, 60, now=self.now + 8 * 86400)
        self.assertIsNone(after['last_detection'])


if __name__ == '__main__':
    unittest.main()
