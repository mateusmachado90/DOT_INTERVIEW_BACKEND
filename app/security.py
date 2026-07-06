import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings


api_token_header = APIKeyHeader(name="X-API-Token", auto_error=False)


def require_api_token(
    api_token: Annotated[str | None, Depends(api_token_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    # Comparacao em tempo constante evita vazamento do token por timing.
    if not api_token or not secrets.compare_digest(api_token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
