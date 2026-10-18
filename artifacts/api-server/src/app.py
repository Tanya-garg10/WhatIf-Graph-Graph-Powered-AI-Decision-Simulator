from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from lib.db import initialize_database
from lib.logger import logger
from routes.health import router as health_router
from routes.graph import router as graph_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    await initialize_database()
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title="WhatIf Graph API",
    description="Graph-powered decision simulator using FalkorDB",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (without prefix to avoid path issues)
app.include_router(health_router, tags=["health"])
app.include_router(graph_router, tags=["whatif"])


@app.get("/")
async def root():
    return {"message": "WhatIf Graph API", "docs": "/docs"}
