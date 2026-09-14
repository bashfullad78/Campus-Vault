"""College Uploader API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes import auth, coins, notes, subjects

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Restricted CORS (§10 roadmap: required in V1). Origins are configuration,
# never "*": browsers outside this list cannot call the API with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(coins.router)
app.include_router(subjects.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
