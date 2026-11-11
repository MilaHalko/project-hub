from fastapi import FastAPI

from project_hub.core.config import Settings
from project_hub.core.error_handlers import register_error_handlers
from project_hub.health.router import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    app = FastAPI(title=settings.name, debug=settings.debug)
    register_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
