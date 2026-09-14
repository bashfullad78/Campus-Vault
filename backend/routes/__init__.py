"""FastAPI HTTP endpoints."""

from backend.routes import auth, coins, notes, subjects

__all__ = ["auth", "coins", "notes", "subjects"]
