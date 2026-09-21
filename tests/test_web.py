"""API authorization, multi-camera ingestion and persistence, no camera required."""
import hashlib
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from apps.backend.main import Settings, create_app
from apps.edge.agent import backend_address, load_sources


def password_hash(password):
    salt = b"0" * 16
    return f"pbkdf2_sha256$300000${salt.hex()}${hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 300000).hex()}"


class WebTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings = Settings(username="admin", password_hash=password_hash("correct-passphrase"),
                                 session_secret=secrets.token_hex(32), edge_token=secrets.token_hex(32),
                                 cameras={"webcam": "Mac", "android": "Phone"},
                                 database=str(Path(self.folder.name) / "events.db"),
                                 public_origin="http://localhost:8080", secure_cookie=False)
        self.ctx = TestClient(create_app(self.settings), base_url="http://localhost:8080")
        self.client = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.folder.cleanup()

    def login(self):
        return self.client.post("/api/login", json={"username": "admin", "password": "correct-passphrase"},
                                headers={"Origin": "http://localhost:8080"})

    def test_password_required_and_origin_checked(self):
        self.assertEqual(self.client.get("/api/cameras").status_code, 401)
        self.assertEqual(self.client.get("/api/insights").status_code, 401)
        self.assertEqual(self.client.post("/api/login", json={"username":"admin","password":"correct-passphrase"}).status_code, 403)
        self.assertEqual(self.client.post("/api/login", json={"username":"admin","password":"bad"}, headers={"Origin":"http://localhost:8080"}).status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(len(self.client.get("/api/cameras").json()), 2)
        self.assertIsNone(self.client.get("/api/insights").json()["last_detection"])
        self.assertEqual(self.client.get("/api/insights?window_minutes=2").status_code, 422)

    def test_edge_token_and_camera_allowlist(self):
        jpeg = b"\xff\xd8example\xff\xd9"
        url = "/api/edge/webcam/frame"
        self.assertEqual(self.client.post(url, content=jpeg, headers={"Content-Type":"image/jpeg"}).status_code, 401)
        auth = {"Authorization": f"Bearer {self.settings.edge_token}", "Content-Type": "image/jpeg"}
        self.assertEqual(self.client.post("/api/edge/unknown/frame", content=jpeg, headers=auth).status_code, 404)
        self.assertEqual(self.client.post(url, content=b"invalid", headers=auth).status_code, 422)
        self.assertEqual(self.client.post(url, content=jpeg, headers={**auth,"X-Maia-Status":"MOVIMIENTO","X-Maia-Event":"appearance"}).status_code, 200)
        self.assertEqual(self.client.get("/api/cameras/webcam/snapshot").status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/cameras/webcam/snapshot").content, jpeg)
        self.assertEqual(self.client.get("/api/events").json()[0]["event"], "appearance")
        self.assertTrue(self.client.get("/api/cameras").json()[0]["online"])
        summary = self.client.get("/api/insights?window_minutes=60").json()
        self.assertEqual(summary["last_detection"]["camera_id"], "webcam")
        self.assertEqual(summary["cameras"][0]["activity_percent"], 100)

    def test_logout(self):
        self.login()
        self.assertEqual(self.client.post("/api/logout", headers={"Origin":"http://localhost:8080"}).status_code, 200)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(self.client.get("/api/insights").status_code, 401)

    def test_edge_config_requires_env_and_https(self):
        self.assertEqual(backend_address("http://localhost:8080"), "http://localhost:8080")
        with self.assertRaises(ValueError):
            backend_address("http://example.org")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cameras.json"
            path.write_text('{"cameras":[{"id":"android","type":"android","source_env":"MAIA_TEST_MISSING_URL"}]}')
            with self.assertRaises(ValueError):
                load_sources(path)


if __name__ == "__main__":
    unittest.main()
