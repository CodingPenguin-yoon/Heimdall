from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import deployments, projects, providers, webhooks


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(get_settings())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Heimdall MVP API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projects.router)
    app.include_router(providers.router)
    app.include_router(deployments.router)
    app.include_router(webhooks.router)

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
