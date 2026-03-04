from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ics import router as ics_router
from app.api.ui import router as ui_router
from app.api.user_feed import router as user_feed_router


def create_app() -> FastAPI:
    app = FastAPI(title="PLANZ")
    app.include_router(health_router)
    app.include_router(ics_router)
    app.include_router(user_feed_router)
    app.include_router(ui_router)
    return app
