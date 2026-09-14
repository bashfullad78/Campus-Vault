"""Application configuration.

Values are loaded from the environment / a .env file at the project root.
All defaults match the "Default limits" section of vision.txt.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ------------------------------------------------------
    APP_NAME: str = "College Uploader"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = True
    # Comma-separated allowed browser origins (§10: restricted CORS is a V1
    # requirement). Defaults cover the React dev server.
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Database ---------------------------------------------------------
    # Required; no default so credentials never live in source. See .env.example.
    DATABASE_URL: str

    # --- JWT / auth ---------------------------------------------------------
    # Dev fallback so local runs work out of the box. Production requires a real
    # SECRET_KEY: get_settings() refuses to boot in production without one.
    SECRET_KEY: str = "dev-insecure-secret-key-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 30
    REFRESH_TOKEN_TTL_DAYS: int = 7

    # --- Upload validation --------------------------------------------------
    MAX_FILE_SIZE_MB: int = 25
    MIN_PAGE_COUNT: int = 1
    MAX_PAGE_COUNT: int = 500

    # --- File storage ---------------------------------------------------------
    # STORAGE_BACKEND selects where note files live:
    #   "local" — ./STORAGE_DIR on the same machine (V1 default; dev use).
    #   "s3"    — any S3-compatible object store (AWS S3, Cloudflare R2,
    #             Backblaze B2, MinIO...) so files survive deploys/restarts.
    STORAGE_BACKEND: str = "local"
    STORAGE_DIR: str = "./storage"

    # S3 settings (required iff STORAGE_BACKEND=s3; validated at boot).
    S3_ENDPOINT_URL: str | None = None  # e.g. https://<acct>.r2.cloudflarestorage.com
    S3_REGION: str = "auto"  # R2/B2 ignore this; AWS needs e.g. us-east-1
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    # Suffix appended at boot to prove credentials actually work (findably,
    # not silently), then removed. Tests use it as a cheap bucket namespace.
    S3_BOOT_CHECK_SUFFIX: str = ".boot-check"

    # --- Coin economy -------------------------------------------------------
    UPLOAD_REWARD: int = 10
    DOWNLOAD_COST: int = 5
    DAILY_REWARD_CAP: int = 5

    # --- Rate limiting (V1: in-process) --------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/minute"
    UPLOAD_RATE_LIMIT: str = "10/minute"


def _validate_storage_settings(s: Settings) -> None:
    """Fail fast on storage misconfiguration at boot, never at first request."""
    if s.STORAGE_BACKEND not in ("local", "s3"):
        raise RuntimeError(
            f"STORAGE_BACKEND must be 'local' or 's3', got {s.STORAGE_BACKEND!r}"
        )
    if s.STORAGE_BACKEND == "s3":
        missing = [
            name
            for name in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
            if not getattr(s, name)
        ]
        if missing:
            raise RuntimeError(
                f"STORAGE_BACKEND=s3 requires these settings: {', '.join(missing)}"
            )
        if not s.S3_ENDPOINT_URL and s.ENVIRONMENT == "production":
            raise RuntimeError(
                "S3_ENDPOINT_URL must be set in production (explicit provider beats "
                "SDK region inference)"
            )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.ENVIRONMENT == "production" and (
        not s.SECRET_KEY or s.SECRET_KEY == "dev-insecure-secret-key-change-me"
    ):
        raise RuntimeError(
            "SECRET_KEY must be set via environment when ENVIRONMENT=production"
        )
    _validate_storage_settings(s)
    return s


settings = get_settings()
