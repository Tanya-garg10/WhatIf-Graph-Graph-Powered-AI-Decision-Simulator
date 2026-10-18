from fastapi import APIRouter
from lib.db import health_check

router = APIRouter(prefix="/api")


@router.get("/healthz")
async def health_check_endpoint():
    """Health check endpoint."""
    is_healthy = await health_check()
    return {"status": "ok" if is_healthy else "degraded"}


# Also support /health for compatibility
@router.get("/health")
async def health_check_endpoint_alt():
    """Health check endpoint (alternate path)."""
    is_healthy = await health_check()
    return {"status": "ok" if is_healthy else "degraded"}
