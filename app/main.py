"""
app/main.py
────────────
FastAPI application factory.

Responsibilities:
  1. Create the FastAPI app instance with metadata for auto-docs.
  2. Register CORS middleware (permissive in dev, tighten in prod).
  3. Wire up the async lifespan context manager which:
       • Connects to MongoDB / Cosmos DB at startup (fetching the URI
         from Azure Key Vault when APP_ENV=production).
       • Initialises Beanie with all Document models (creates indexes).
       • Gracefully closes the Motor client on shutdown.
  4. Mount all API routers under their respective prefixes.
  5. Expose a /health endpoint for Azure Container Apps health probes.

Beanie model registration order:
  BaseIngredient must be registered before its subclasses so that the
  polymorphic union type is fully constructed before Beanie builds indexes.
  The subclass list order does not matter beyond that.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from beanie import init_beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.admin.routes import ingredients as admin_ingredients
from app.admin.routes import cache as admin_cache
from app.api.routes import auth, cosmic, metadata, recipe, stories, users
from app.config.settings import get_settings
from app.models.ingredients import (
    BaseIngredient,
    Breathing,
    Chanting,
    GitaVerse,
    Punya,
    Reflection,
    Story,
    Yoga,
)
from app.models.panchang import DailyPanchang
from app.models.recipe_request import RecipeRequest
from app.models.user import User

settings = get_settings()


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application-wide resources across the process lifetime.

    Startup:
      • Resolves the MongoDB connection string (env var in LOCAL mode,
        Azure Key Vault in PRODUCTION mode via Managed Identity).
      • Creates an AsyncIOMotorClient (non-blocking MongoDB driver).
      • Calls init_beanie() which:
          - Registers all Document models.
          - Creates MongoDB indexes defined in each model's Settings class.
          - Wires up the polymorphic discriminator for BaseIngredient.

    Shutdown:
      • Closes the Motor client to release connection pool resources.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    mongodb_url = settings.get_mongodb_url()
    motor_client: AsyncIOMotorClient = AsyncIOMotorClient(mongodb_url)

    await init_beanie(
        database=motor_client[settings.DATABASE_NAME],
        document_models=[
            User,
            # BaseIngredient FIRST — required for polymorphic union setup.
            BaseIngredient,
            GitaVerse,
            Yoga,
            Breathing,
            Chanting,
            Punya,
            Story,
            Reflection,
            DailyPanchang,
            RecipeRequest,
        ],
    )

    yield  # ← Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    motor_client.close()


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "**Dharma AI** – A Hindu spirituality companion for the rational mind.\n\n"
        "This API serves the React Native mobile application with:\n"
        "- OTP-based mobile authentication (JWT)\n"
        "- AI-personalised daily spiritual recipes\n"
        "- Panchang (Hindu almanac) data with scientific inferences\n"
        "- Shuffle stories from Hindu scripture\n"
        "- User profile and streak management\n\n"
        "**Authentication:** All protected endpoints require "
        "`Authorization: Bearer <token>` obtained from `POST /auth/verify-otp`."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(recipe.router)
app.include_router(cosmic.router)
app.include_router(stories.router)
app.include_router(metadata.router)
app.include_router(admin_ingredients.router)
app.include_router(admin_cache.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_description="Returns 200 OK when the service is ready.",
)
async def health_check() -> dict:
    """
    Lightweight liveness probe used by Azure Container Apps.

    Configure the Container App startup probe to call `GET /health`.
    The endpoint returns 200 as soon as the process is ready (Beanie
    has finished initialising, indexes are created).
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV.value,
    }
