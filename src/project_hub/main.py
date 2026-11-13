from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.router import router as auth_router
from project_hub.auth.tokens import TokenService
from project_hub.core.config import Settings
from project_hub.core.error_handlers import register_error_handlers
from project_hub.db.database import create_database
from project_hub.health.router import router as health_router
from project_hub.users.router import router as users_router


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if settings.database_url is None:
            app.state.database = None
            yield
            return
        database = create_database(settings)
        await database.open()
        app.state.database = database
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(title=settings.name, debug=settings.debug, lifespan=lifespan)
    app.state.password_hasher = PasswordHasher()
    app.state.token_service = (
        TokenService(settings.jwt_secret.get_secret_value()) if settings.jwt_secret else None
    )
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(users_router)
    return app


app = create_app()
