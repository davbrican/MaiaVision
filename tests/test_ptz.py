"""No physical cameras needed: validate authentication, queuing, and edge config."""
import hashlib
import json
import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.backend.main import Settings, create_app
from apps.backend.ptz import PtzMailbox
from apps.edge.agent import load_sources, rotate_frame
from apps.edge.ptz import PtzConfig, direction_velocity, parse_ptz


class PtzTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        salt = b"0" * 16
        hash_ = hashlib.pbkdf2_hmac("sha256", b"password-for-testing", salt, 300000).hex()
        settings = Settings("admin", f"pbkdf2_sha256$300000${salt.hex()}${hash_}",
                            secrets.token_hex(32), secrets.token_hex(32),
                            {"tapo1": "Salón", "webcam": "Webcam"},
                            database=str(Path(self.folder.name) / "data.db"),
                            public_origin="http://localhost:8080", secure_cookie=False)
        self.edge_auth = {"Authorization": f"Bearer {settings.edge_token}"}
        self.ctx = TestClient(create_app(settings), base_url="http://localhost:8080")
        self.client = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.folder.cleanup()

    def login(self):
        response = self.client.post("/api/login", json={"username": "admin", "password": "password-for-testing"},
                                    headers={"Origin": "http://localhost:8080"})
        self.assertEqual(response.status_code, 200)

    def test_ptz_rejects_unauthenticated_and_unknown_and_offline(self):
        url = "/api/cameras/tapo1/ptz"
        self.assertEqual(self.client.post(url, json={"direction": "left"}).status_code, 401)
        self.login()
        self.assertEqual(self.client.post(url, json={"direction": "left"}).status_code, 403)
        headers = {"Origin": "http://localhost:8080"}
        self.assertEqual(self.client.post("/api/cameras/missing/ptz", json={"direction": "left"}, headers=headers).status_code, 404)
        self.assertEqual(self.client.post(url, json={"direction": "hack"}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post(url, json={"direction": "left"}, headers=headers).status_code, 409)
        self.assertEqual(self.client.get("/api/edge/tapo1/ptz/commands").status_code, 401)
        self.assertEqual(self.client.get("/api/edge/missing/ptz/commands", headers=self.edge_auth).status_code, 404)

    def test_edge_poll_control_and_no_old_command_replay(self):
        video_url = "/api/edge/tapo1/frame"
        jpeg = b"\xff\xd8image\xff\xd9"
        response = self.client.post(video_url, content=jpeg,
                                    headers={**self.edge_auth, "Content-Type": "image/jpeg"})
        self.assertEqual(response.status_code, 200)
        self.login()
        headers = {"Origin": "http://localhost:8080"}
        url = "/api/cameras/tapo1/ptz"
        self.assertEqual(self.client.post(url, json={"direction": "right"}, headers=headers).status_code, 409)
        initial = self.client.get("/api/edge/tapo1/ptz/commands", headers=self.edge_auth).json()
        self.assertEqual(initial, {"sequence": 0, "commands": []})
        self.assertTrue(self.client.get("/api/cameras").json()[0]["ptz"])
        response = self.client.post(url, json={"direction": "right"}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["queued"])
        command = self.client.get("/api/edge/tapo1/ptz/commands?since=0", headers=self.edge_auth).json()
        self.assertEqual(command["commands"][0]["direction"], "right")
        self.assertEqual(self.client.post(url, json={"direction": "left"}, headers=headers).status_code, 429)
        self.assertEqual(self.client.post(url, json={"direction": "stop"}, headers=headers).status_code, 200)
        stopped = self.client.get("/api/edge/tapo1/ptz/commands?since=0", headers=self.edge_auth).json()
        self.assertEqual([c["direction"] for c in stopped["commands"]], ["stop"])
        # Restarted edge requests no 'since': never replay a queued command.
        restart = self.client.get("/api/edge/tapo1/ptz/commands", headers=self.edge_auth).json()
        self.assertEqual(restart["commands"], [])
        self.assertEqual(restart["sequence"], stopped["sequence"])
        self.assertEqual(self.client.get("/api/edge/tapo1/ptz/commands?since=-1", headers=self.edge_auth).status_code, 422)

    def test_mailbox_ttl_prevents_late_camera_movement(self):
        mailbox = PtzMailbox({"tapo1"})
        mailbox.poll("tapo1", None)
        sequence = mailbox.send("tapo1", "up")
        with patch("apps.backend.ptz.time.monotonic", return_value=time.monotonic() + 4):
            result = mailbox.poll("tapo1", 0)
        self.assertEqual(result["sequence"], sequence)
        self.assertEqual(result["commands"], [])

    def test_config_rotation_ptz_private_env_and_no_credentials_in_json(self):
        config = {"host_env": "MV_TEST_HOST", "user_env": "MV_TEST_USER",
                  "password_env": "MV_TEST_PASSWORD", "invert_tilt": True}
        with patch.dict(os.environ, {"MV_TEST_HOST": "192.168.1.150", "MV_TEST_USER": "camera-user",
                                     "MV_TEST_PASSWORD": "local-password", "MV_TEST_RTSP": "rtsp://camera.invalid/stream1"}):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "camera.json"
                path.write_text(json.dumps({"cameras": [{"id": "tapo1", "type": "rtsp",
                                  "source_env": "MV_TEST_RTSP", "rotation": 180, "ptz": config}]}))
                camera = load_sources(path)[0]
                self.assertEqual(camera.rotation, 180)
                self.assertEqual(camera.ptz.host, "192.168.1.150")
                self.assertEqual(direction_velocity("up", camera.ptz), (0.0, -0.35))
                self.assertNotIn("local-password", path.read_text())
                for invalid_rotation in [45, True, "180"]:
                    document = json.loads(path.read_text())
                    document["cameras"][0]["rotation"] = invalid_rotation
                    path.write_text(json.dumps(document))
                    with self.assertRaises(ValueError):
                        load_sources(path)
                    document["cameras"][0]["rotation"] = 180
                    path.write_text(json.dumps(document))
        with patch.dict(os.environ, {"MV_TEST_HOST": "8.8.8.8", "MV_TEST_USER": "test",
                                     "MV_TEST_PASSWORD": "test"}):
            with self.assertRaises(ValueError):
                parse_ptz(config, "tapo1")
        self.assertEqual(direction_velocity("left", PtzConfig("192.168.1.1", "u", "p", invert_pan=True)), (0.35, 0.0))
        frame = object()
        self.assertIs(rotate_frame(frame, 0), frame)  # Does not import OpenCV in no-rotation case.


if __name__ == "__main__":
    unittest.main()
