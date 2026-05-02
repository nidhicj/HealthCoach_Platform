"""Shared FastAPI dependencies and pagination utilities for P3 domain routes."""
import base64
from datetime import datetime
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import current_tenant, require_role
from src.auth.jwt_utils import TokenClaims
from src.db.session import get_db

# ── type aliases ───────────────────────────────────────────────────────────────

HcClaimsDep = Annotated[TokenClaims, Depends(require_role("hc"))]
ClientClaimsDep = Annotated[TokenClaims, Depends(require_role("client"))]
TenantDep = Annotated[str, Depends(current_tenant)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
LimitDep = Annotated[int, Query(ge=1, le=100, description="Page size (1–100, default 20)")]

# ── pagination ─────────────────────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedList(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc
