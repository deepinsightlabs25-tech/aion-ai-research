import os
from typing import Optional

import requests
from fastapi import Header, HTTPException, status

TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
AUTH_DISABLED_ENV = "AUTH_DISABLED"
GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
DEFAULT_GOOGLE_CLIENT_ID = "175829896291-kurqbip4mo4h75kgnno5lr54qnef1tsl.apps.googleusercontent.com"


def _is_auth_disabled() -> bool:
    return os.getenv(AUTH_DISABLED_ENV, "false").strip().lower() == "true"


def _get_google_client_id() -> str:
    return os.getenv(GOOGLE_CLIENT_ID_ENV, "").strip() or DEFAULT_GOOGLE_CLIENT_ID


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _unauthorized("Missing authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Authorization header must be a Bearer token")
    return token.strip()


def verify_google_id_token(id_token: str) -> dict:
    client_id = _get_google_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server auth is not configured. GOOGLE_CLIENT_ID is missing.",
        )

    try:
        response = requests.get(
            TOKEN_INFO_URL,
            params={"id_token": id_token},
            timeout=8,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify Google token right now. Please retry.",
        ) from exc

    if response.status_code != status.HTTP_200_OK:
        raise _unauthorized("Invalid or expired Google token")

    payload = response.json()
    if payload.get("aud") != client_id:
        raise _unauthorized("Token audience mismatch")

    return {
        "sub": payload.get("sub", ""),
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if _is_auth_disabled():
        return {
            "sub": "dev-user",
            "email": "dev@example.com",
            "name": "Developer",
            "picture": None,
        }

    token = _extract_bearer_token(authorization)
    return verify_google_id_token(token)
