from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

import bcrypt
from fastapi import HTTPException, Request

from web_admin.utils.db import get_db_connection


LOGGER = logging.getLogger(__name__)

JWT_COOKIE_NAME = "admin_access_token"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ADMIN_TOKEN_EXPIRE_MINUTES", "480")) * 60
PASSWORD_ITERATIONS = 260_000

def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("ADMIN_JWT_SECRET")
    if secret:
        return secret

    secret_path = Path(__file__).resolve().parents[2] / "data" / "admin_jwt_secret.key"
    try:
        if secret_path.exists():
            secret = secret_path.read_text(encoding="utf-8").strip()
            if secret:
                return secret
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_urlsafe(48)
        secret_path.write_text(secret, encoding="utf-8")
        LOGGER.warning(
            "JWT_SECRET_KEY is not set. Generated persistent local admin JWT secret at %s.",
            secret_path,
        )
        return secret
    except OSError:
        LOGGER.warning("Could not persist admin JWT secret; sessions will be invalidated on restart.")
        return secrets.token_urlsafe(48)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
        except ValueError:
            return False

    # Legacy compatibility for admin rows created before the bcrypt migration.
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("ascii"),
            int(iterations_raw),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def create_access_token(username: str) -> str:
    now = int(time.time())
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": username,
        "role": "admin",
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        _jwt_secret().encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> Optional[Dict[str, object]]:
    try:
        header_raw, payload_raw, signature_raw = token.split(".", 2)
        signing_input = f"{header_raw}.{payload_raw}"
        expected_signature = hmac.new(
            _jwt_secret().encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64url_decode(signature_raw), expected_signature):
            return None

        header = json.loads(_b64url_decode(header_raw))
        if header.get("alg") != JWT_ALGORITHM:
            return None

        payload = json.loads(_b64url_decode(payload_raw))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("role") != "admin" or not payload.get("sub"):
            return None
        return payload
    except Exception:
        return None


def ensure_admin_schema() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP NULL,
                UNIQUE KEY uk_admin_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        conn.commit()
    finally:
        conn.close()


def _admin_count() -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) AS cnt FROM admin_users")
        row = cursor.fetchone()
        return int(row["cnt"] if row else 0)
    finally:
        conn.close()


def create_or_update_admin(username: str, password: str, update_existing: bool = False) -> None:
    ensure_admin_schema()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM admin_users WHERE username = %s", (username,))
        row = cursor.fetchone()
        password_hash = hash_password(password)
        if row and update_existing:
            cursor.execute(
                "UPDATE admin_users SET password_hash = %s, is_active = 1 WHERE username = %s",
                (password_hash, username),
            )
        elif not row:
            cursor.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
        conn.commit()
    finally:
        conn.close()


def ensure_seed_admin_user() -> None:
    ensure_admin_schema()

    username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    password = os.getenv("ADMIN_PASSWORD")
    if password:
        create_or_update_admin(username, password, update_existing=False)
        return

    if _admin_count() > 0:
        return

    bootstrap_password = secrets.token_urlsafe(18)
    create_or_update_admin(username, bootstrap_password, update_existing=False)

    credentials_path = Path(__file__).resolve().parents[2] / "data" / "admin_bootstrap_credentials.txt"
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(
        f"username={username}\npassword={bootstrap_password}\n",
        encoding="utf-8",
    )
    LOGGER.warning(
        "Created bootstrap admin account. Credentials were written to %s. "
        "Set ADMIN_PASSWORD in .env and rotate this password after first login.",
        credentials_path,
    )


def authenticate_admin(username: str, password: str) -> Optional[Dict[str, object]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, username, password_hash, is_active
            FROM admin_users
            WHERE username = %s
            LIMIT 1
            """,
            (username,),
        )
        user = cursor.fetchone()
        if not user or not user.get("is_active"):
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        cursor.execute("UPDATE admin_users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
        conn.commit()
        return {"id": user["id"], "username": user["username"]}
    finally:
        conn.close()


def get_current_admin(request: Request) -> Optional[Dict[str, object]]:
    token = request.cookies.get(JWT_COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None

    username = str(payload["sub"])
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, username, is_active
            FROM admin_users
            WHERE username = %s
            LIMIT 1
            """,
            (username,),
        )
        user = cursor.fetchone()
        if not user or not user.get("is_active"):
            return None
        return {"id": user["id"], "username": user["username"]}
    finally:
        conn.close()


def require_admin(request: Request) -> Dict[str, object]:
    user = get_current_admin(request)
    if user:
        request.state.admin_user = user
        return user

    if request.url.path.startswith("/api/"):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    next_path = quote(str(request.url.path), safe="/")
    raise HTTPException(status_code=303, headers={"Location": f"/login?next={next_path}"})
