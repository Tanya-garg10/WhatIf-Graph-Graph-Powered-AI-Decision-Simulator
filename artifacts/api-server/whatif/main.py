from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .graph_store import FalkorGraphStore, GraphStore, GraphUnavailable
from .simulation import _openai_client, simulate

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("whatif-api")


def _create_graph_store() -> GraphStore:
    return FalkorGraphStore.from_environment()


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = _create_graph_store()
    app.state.graph_store = store
    app.state.ai_client = _openai_client()
    if store.backend == "falkordb" and not store.database_connected:
        logger.error("Configured FalkorDB is unavailable; requests will return an explicit error.")
    yield
    store.close()


app = FastAPI(
    title="WhatIf Graph API",
    description="Graph-powered scenario impact analysis with an explicit local demo mode.",
    version="1.0.0",
    lifespan=lifespan,
)


class ScenarioInput(BaseModel):
    scenario: str = Field(min_length=5, max_length=500)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]


@app.get("/api/healthz", response_model=HealthResponse)
def health(request: Request) -> dict[str, str]:
    store: GraphStore = request.app.state.graph_store
    status = "degraded" if store.backend == "falkordb" and not store.database_connected else "ok"
    return {"status": status}


@app.get("/api/graph")
def get_graph(request: Request) -> dict:
    store: GraphStore = request.app.state.graph_store
    try:
        nodes, edges = store.get_graph()
    except GraphUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "nodes": nodes,
        "edges": edges,
        "backend": store.backend,
        "databaseConnected": store.database_connected,
        "aiConfigured": request.app.state.ai_client is not None,
        "graphName": store.graph_name,
    }


@app.post("/api/simulate")
def simulate_scenario(payload: ScenarioInput, request: Request) -> dict:
    store: GraphStore = request.app.state.graph_store
    try:
        return simulate(payload.scenario, store, request.app.state.ai_client)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GraphUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "WhatIf Graph API", "docs": "/docs"}
