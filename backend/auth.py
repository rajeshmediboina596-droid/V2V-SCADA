"""
Authentication & Role-Based Access Control (RBAC) Module for V2V-SCADA.
Provides lightweight, token-based authorization suitable for edge SCADA platforms.

Roles Hierarchy:
    admin (3)    -> Full system control, demo trigger, spoof tests, commands, reports, telemetry
    operator (2) -> SCADA dispatch commands, report generation, telemetry ingestion, read access
    viewer (1)   -> Read-only telemetry, map monitoring, diagnostics, health metrics

Modes:
    - DEMO MODE (API_AUTH_ENABLED=False): Transparent access granted as admin for zero-friction demonstration.
    - SECURE MODE (API_AUTH_ENABLED=True): Requires valid API Key / Bearer Token with role enforcement.
"""

from typing import Optional, Dict, Any, Callable
from fastapi import Request, HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
import hmac
import logging

from backend import config

logger = logging.getLogger("v2v_auth")

ROLE_LEVELS: Dict[str, int] = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _resolve_role_from_token(token: str) -> Optional[str]:
    """
    Constant-time lookup to resolve role from provided API key/token.
    Prevents timing side-channel attacks.
    """
    if not token:
        return None

    token_bytes = token.strip().encode("utf-8")

    if config.API_ADMIN_KEY and hmac.compare_digest(token_bytes, config.API_ADMIN_KEY.encode("utf-8")):
        return "admin"
    if config.API_OPERATOR_KEY and hmac.compare_digest(token_bytes, config.API_OPERATOR_KEY.encode("utf-8")):
        return "operator"
    if config.API_VIEWER_KEY and hmac.compare_digest(token_bytes, config.API_VIEWER_KEY.encode("utf-8")):
        return "viewer"

    return None


async def get_current_user(
    request: Request,
    header_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Dict[str, Any]:
    """
    Resolves client identity and role.
    If API_AUTH_ENABLED is False (DEMO mode), grants default admin role.
    """
    if not config.API_AUTH_ENABLED:
        return {
            "authenticated": False,
            "role": "admin",
            "mode": "demo_unrestricted",
            "user_id": "demo_operator",
        }

    # Extract token from X-API-Key, Authorization Bearer, or query parameter
    token = header_key
    if not token and bearer_creds:
        token = bearer_creds.credentials
    if not token:
        token = request.query_params.get("api_key")

    if not token:
        logger.warning(f"Unauthenticated request to protected endpoint: {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required. Provide X-API-Key header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = _resolve_role_from_token(token)
    if not role:
        logger.warning(f"Invalid API token presented for {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "authenticated": True,
        "role": role,
        "mode": "secure",
        "user_id": f"role_{role}",
    }


def require_role(min_role: str) -> Callable:
    """
    Dependency factory enforcing role level hierarchy:
    viewer (1) <= operator (2) <= admin (3)
    """
    required_level = ROLE_LEVELS.get(min_role.lower(), 1)

    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role", "viewer")
        user_level = ROLE_LEVELS.get(user_role, 0)

        if user_level < required_level:
            logger.warning(
                f"Access forbidden: User with role '{user_role}' attempted to access "
                f"endpoint requiring '{min_role}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires '{min_role}' role or higher.",
            )
        return user

    return role_checker
