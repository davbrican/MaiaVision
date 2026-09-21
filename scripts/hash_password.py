"""Generate a salted PBKDF2 hash; do not place passwords on the command line."""
import getpass
import hashlib
import secrets

password = getpass.getpass("Contraseña de acceso (mínimo 12 caracteres): ")
if len(password) < 12:
    raise SystemExit("La contraseña debe tener al menos 12 caracteres")
salt = secrets.token_bytes(16)
rounds = 600_000
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
print(f"MAIA_ADMIN_PASSWORD_HASH='pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}'")
