from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth.api_utils import get_current_user
from auth.jwt_manager import auth_manager
from auth.session_manager import session_manager
from models.database import get_user_by_email, update_user_db
from werkzeug.security import check_password_hash, generate_password_hash
import redis
import os
from config import Config

# Redis brute-force key prefix
_redis_client = redis.Redis(host=os.getenv('REDIS_HOST', Config.REDIS_HOST), port=int(os.getenv('REDIS_PORT', Config.REDIS_PORT)), db=3)
LOGIN_ATTEMPT_KEY = 'login:attempts:'
MAX_LOGIN_ATTEMPTS = 6
LOCKOUT_SECONDS = 300

router = APIRouter(prefix="/api/mobile/v1/auth", tags=["mobile-auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
def mobile_login(payload: LoginRequest):
    # Basic brute-force protection (per-email)
    attempt_key = LOGIN_ATTEMPT_KEY + payload.email
    attempts = 0
    try:
        attempts = int(_redis_client.get(attempt_key) or 0)
    except Exception:
        attempts = 0
    if attempts >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too_many_attempts")

    user = get_user_by_email(payload.email)
    if not user:
        try:
            _redis_client.incr(attempt_key)
            _redis_client.expire(attempt_key, LOCKOUT_SECONDS)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="invalid_credentials")

    # Support legacy hashes created by Flask app (werkzeug)
    stored_hash = user.get("password_hash")
    if not stored_hash or not check_password_hash(stored_hash, payload.password):
        try:
            _redis_client.incr(attempt_key)
            _redis_client.expire(attempt_key, LOCKOUT_SECONDS)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="invalid_credentials")

    token_data = {
        "email": user.get("email"),
        "role": user.get("role", "user"),
        "parent_email": user.get("parent_email"),
        "company_name": user.get("company_name")
    }

    access_token = auth_manager.create_access_token(token_data)
    refresh_token = auth_manager.create_refresh_token(token_data)
    # Reset failed attempts on success
    try:
        _redis_client.delete(attempt_key)
    except Exception:
        pass

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 60 * 24 * 60  # clients should use refresh
        }
    }


@router.post("/refresh")
def mobile_refresh(payload: RefreshRequest):
    from jwt import InvalidTokenError
    import time

    payload_data = auth_manager.decode_token(payload.refresh_token, expected_type="refresh")
    if not payload_data:
        raise HTTPException(status_code=401, detail="invalid_refresh_token")

    # Blacklist previous refresh token jti (rotation)
    old_jti = payload_data.get("jti")
    exp = payload_data.get("exp")
    if old_jti and exp:
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = max(0, int(exp) - now)
        try:
            session_manager.blacklist_token(old_jti, ttl)
        except Exception:
            pass

    # Issue new tokens
    token_data = {
        "email": payload_data.get("email"),
        "role": payload_data.get("role"),
        "parent_email": payload_data.get("parent_email"),
        "company_name": payload_data.get("company_name")
    }
    new_access = auth_manager.create_access_token(token_data)
    new_refresh = auth_manager.create_refresh_token(token_data)

    return {"status": "success", "data": {"access_token": new_access, "refresh_token": new_refresh}}


@router.post("/logout")
def mobile_logout(request: LogoutRequest, req: Request):
    # Blacklist access token from header if provided
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split()[1]
        payload = auth_manager.decode_token(token, expected_type="access")
        if payload and payload.get("jti") and payload.get("exp"):
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = max(0, int(payload.get("exp")) - now)
            try:
                session_manager.blacklist_token(payload.get("jti"), ttl)
            except Exception:
                pass

    # Blacklist refresh token if provided
    if request.refresh_token:
        r_payload = auth_manager.decode_token(request.refresh_token, expected_type="refresh")
        if r_payload and r_payload.get("jti") and r_payload.get("exp"):
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = max(0, int(r_payload.get("exp")) - now)
            try:
                session_manager.blacklist_token(r_payload.get("jti"), ttl)
            except Exception:
                pass

    return {"status": "success"}


@router.post("/change-password")
def mobile_change_password(payload: ChangePasswordRequest, user=Depends(get_current_user)):
    email = user.get("email")
    u = get_user_by_email(email)
    if not u:
        raise HTTPException(status_code=404, detail="user_not_found")

    if not check_password_hash(u.get("password_hash", ""), payload.old_password):
        raise HTTPException(status_code=400, detail="invalid_old_password")

    new_hash = generate_password_hash(payload.new_password)
    update_user_db(email, {"password_hash": new_hash})

    # Revoke existing sessions for this user
    try:
        session_manager.revoke_user_sessions(email)
    except Exception:
        pass

    return {"status": "success"}


@router.post("/forgot-password")
def mobile_forgot_password(body: dict):
    # Reuse existing server-side helper from Flask auth module
    try:
        from routes.auth import _create_reset_token, _send_reset_email
    except Exception:
        raise HTTPException(status_code=500, detail="server_error")

    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="missing_email")

    token = _create_reset_token(email)
    base = "https://" + body.get("host", "") if body.get("host") else ""
    reset_link = f"{base}/reset-password/{token}" if base else f"/reset-password/{token}"
    try:
        _send_reset_email(email, reset_link)
    except Exception:
        pass

    return {"status": "success"}
