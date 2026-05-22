"""Entry point: starts the gRPC server (background task) and the FastAPI sidecar.

The FastAPI sidecar exposes /health and /metrics for Prometheus.
The gRPC server exposes Redact() on port 50051.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.grpc_server import serve as serve_grpc


@asynccontextmanager
async def lifespan(_: FastAPI):
    grpc_task = asyncio.create_task(serve_grpc())
    try:
        yield
    finally:
        grpc_task.cancel()


app = FastAPI(
    title="omnibank-pii-filter",
    version=os.getenv("GIT_SHA", "dev"),
    lifespan=lifespan,
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "grpc_port": 50051}
