import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from project_hub.auth.passwords import PasswordHasher
from project_hub.auth.router import router as auth_router
from project_hub.auth.tokens import TokenService
from project_hub.core.config import Settings
from project_hub.core.error_handlers import register_error_handlers
from project_hub.core.logging import configure_logging
from project_hub.db.database import create_database
from project_hub.documents.router import router as documents_router
from project_hub.documents.upload_limit import UploadLimitMiddleware
from project_hub.health.router import router as health_router
from project_hub.mail.mailer import create_mailer
from project_hub.projects.router import router as projects_router
from project_hub.shares.no_store import NoStoreMiddleware
from project_hub.shares.router import router as shares_router
from project_hub.storage.s3 import create_s3_storage
from project_hub.users.router import router as users_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    if settings is None:
        settings = Settings()
    if settings.jwt_secret is None:
        logger.warning("APP_JWT_SECRET is not set; login is disabled")
    storage = create_s3_storage(settings)

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
    app.state.settings = settings
    app.state.storage = storage
    app.state.mailer = create_mailer(settings)
    app.state.password_hasher = PasswordHasher()
    app.state.token_service = (
        TokenService(settings.jwt_secret.get_secret_value()) if settings.jwt_secret else None
    )
    register_error_handlers(app)
    app.add_middleware(UploadLimitMiddleware)
    app.add_middleware(NoStoreMiddleware)
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(users_router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    app.include_router(shares_router)
    return app


app = create_app()
