from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    trakt_client_id: str
    trakt_client_secret: str
    trakt_redirect_uri: str
    public_base_url: str
    calendar_token: str
    data_dir: Path
    days_ahead: int
    days_back: int
    timezone: str
    include_premieres: bool
    include_new_shows: bool
    include_finales: bool
    cache_seconds: int


def load_settings() -> Settings:
    port = os.getenv("PORT", "8765")
    public_base_url = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{port}").rstrip("/")
    redirect_uri = os.getenv("TRAKT_REDIRECT_URI", f"{public_base_url}/auth/callback")
    data_dir = Path(os.getenv("DATA_DIR", "data"))

    return Settings(
        trakt_client_id=os.getenv("TRAKT_CLIENT_ID", "").strip(),
        trakt_client_secret=os.getenv("TRAKT_CLIENT_SECRET", "").strip(),
        trakt_redirect_uri=redirect_uri.strip(),
        public_base_url=public_base_url,
        calendar_token=os.getenv("CALENDAR_TOKEN", secrets.token_urlsafe(32)),
        data_dir=data_dir,
        days_ahead=max(1, int(os.getenv("DAYS_AHEAD", "90"))),
        days_back=max(0, int(os.getenv("DAYS_BACK", "1"))),
        timezone=os.getenv("TIMEZONE", "America/Moncton"),
        include_premieres=_truthy(os.getenv("INCLUDE_PREMIERES"), True),
        include_new_shows=_truthy(os.getenv("INCLUDE_NEW_SHOWS"), False),
        include_finales=_truthy(os.getenv("INCLUDE_FINALES"), True),
        cache_seconds=max(60, int(os.getenv("CACHE_SECONDS", "21600"))),
    )
