from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing needed yet (Alembic handles migrations externally)
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="Financing API",
        version="0.1.0",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV == "development" else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1 import applications, auth, borrowers, loans, partners, products, webhooks

    for router in [products.router, partners.router, borrowers.router,
                   applications.router, loans.router, webhooks.router, auth.router]:
        app.include_router(router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
