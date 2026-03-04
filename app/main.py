from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ics import router as ics_router


def create_app() -> FastAPI:
    app = FastAPI(title="PLANZ")
    app.include_router(health_router)
    app.include_router(ics_router)
    return app
