"""ONVIF adapter contract with mocked hardware; a real C200C must still be tested."""
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apps.edge.ptz import OnvifPtz, PtzConfig


class StubPtzService:
    def __init__(self):
        self.moves = []
        self.stops = []

    def GetConfigurationOptions(self, request):
        assert request['ConfigurationToken'] == 'config-token'
        return SimpleNamespace(Spaces=SimpleNamespace(ContinuousPanTiltVelocitySpace=[SimpleNamespace(URI='urn:ptz:test')]))

    def ContinuousMove(self, request):
        self.moves.append(request)

    def Stop(self, request):
        self.stops.append(request)


class FakeOnvifCamera:
    ptz = StubPtzService()

    def __init__(self, host, port, username, password):
        assert (host, port, username, password) == ('192.168.1.150', 2020, 'camera', 'password')

    def create_media_service(self):
        return SimpleNamespace(GetProfiles=lambda: [SimpleNamespace(token='profile-token',
                                    PTZConfiguration=SimpleNamespace(token='config-token'))])

    def create_ptz_service(self):
        return self.ptz


class OnvifTests(unittest.TestCase):
    def test_continuous_move_timeout_stop_and_inverted_direction(self):
        FakeOnvifCamera.ptz = StubPtzService()
        config = PtzConfig('192.168.1.150', 'camera', 'password', invert_pan=True)
        with patch.dict(sys.modules, {'onvif': types.SimpleNamespace(ONVIFCamera=FakeOnvifCamera)}):
            controller = OnvifPtz(config)
        with patch('apps.edge.ptz.time.sleep'):
            controller.execute('left')
        self.assertEqual(len(FakeOnvifCamera.ptz.moves), 1)
        command = FakeOnvifCamera.ptz.moves[0]
        self.assertEqual(command['ProfileToken'], 'profile-token')
        self.assertEqual(command['Timeout'], 'PT1S')
        self.assertEqual(command['Velocity']['PanTilt']['x'], 0.35)
        self.assertEqual(command['Velocity']['PanTilt']['space'], 'urn:ptz:test')
        self.assertEqual(len(FakeOnvifCamera.ptz.stops), 1)
        controller.execute('stop')
        self.assertEqual(len(FakeOnvifCamera.ptz.stops), 2)

    def test_stop_also_runs_if_move_raises(self):
        FakeOnvifCamera.ptz = StubPtzService()
        def reject(_):
            raise RuntimeError('simulated ONVIF failure')
        FakeOnvifCamera.ptz.ContinuousMove = reject
        with patch.dict(sys.modules, {'onvif': types.SimpleNamespace(ONVIFCamera=FakeOnvifCamera)}):
            controller = OnvifPtz(PtzConfig('192.168.1.150', 'camera', 'password'))
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            controller.execute('up')
        self.assertEqual(len(FakeOnvifCamera.ptz.stops), 1)


if __name__ == '__main__':
    unittest.main()
