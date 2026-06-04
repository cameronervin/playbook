"""FastAPI application — composition root.

Wires together all components but contains no implementation details.
Infrastructure lifecycle is owned by the lifespan, in this order:

    observability -> llm -> kb -> storage -> checkpointer -> graph compile
    -> executors -> yield -> reverse cleanup

The agent layer (app/agents/**) is owned by a separate module. It is wired here
inside a clearly-commented try/except block so this file still imports and the
API still boots even when the agent layer is stubbed or absent.
"""

import sys

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import health
from app.core.config import settings
from app.core.exception_handlers import (
    app_error_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AppError
from app.infrastructure.checkpointer import (
    cleanup_checkpointer_pool,
    create_checkpointer,
    create_checkpointer_pool,
)
from app.infrastructure.db.session import cleanup_db_engine, get_db
from app.infrastructure.knowledgebase import get_kb_provider, is_kb_feature_enabled
from app.infrastructure.llm import get_llm_provider
from app.infrastructure.storage import cleanup_storage_provider, get_storage_provider
from app.middleware import setup_cors
from app.observability.agent_trace import verify_tracing_configuration

logger = structlog.get_logger(__name__)

API_V1_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"

OPENAPI_TAGS = [
    {"name": "Health", "description": "Platform liveness and dependency health checks."},
]


async def _init_infrastructure(app: FastAPI) -> tuple:
    """Initialize all infrastructure components in startup order.

    Returns:
        Tuple of (checkpointer_pool, kb_provider) needed for shutdown cleanup.
    """
    checkpointer_pool = None
    kb_provider = None

    # 1. Observability
    tracing_status = verify_tracing_configuration()
    logger.info("tracing_startup_check", **tracing_status)

    # 2. LLM provider
    llm_provider = get_llm_provider()
    chat_model = llm_provider.get_chat_model()
    logger.info("Initialized LLM provider", provider=llm_provider.provider_name, mode=settings.LLM_PROVIDER_MODE)

    # 3. Knowledgebase provider
    if is_kb_feature_enabled():
        kb_provider = get_kb_provider()
        logger.info(
            "Initialized knowledgebase provider",
            provider=kb_provider.provider_name,
            mode=settings.KB_PROVIDER_MODE,
        )
        try:
            config_id = await kb_provider.resolve_configuration()
            logger.info("KB configuration resolved", config_id=config_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "KB configuration not resolved at startup — retrieval may fail "
                "until the KB service is reachable",
                error=str(exc),
            )
    else:
        logger.info("Knowledgebase disabled (KB_ENABLED=false)")

    # 4. Storage
    storage = get_storage_provider()
    logger.info("Initialized storage provider")

    # 5. Checkpointer
    checkpointer_pool = await create_checkpointer_pool()
    checkpointer = await create_checkpointer(checkpointer_pool)
    logger.info("Created checkpointer connection pool")

    # 6 & 7. LangGraph graph compile + executors (AGENT LAYER WIRED HERE)
    # ---------------------------------------------------------------------
    # The agent layer (app/agents/**) is owned separately. It is expected to
    # expose `compile_example_graph(...)` and an `ExampleExecutor`. Wrapped in
    # try/except so a stubbed/absent agent layer never blocks API startup —
    # dependency injection will raise a clear error at first dispatch instead.
    example_executor = None
    try:
        from app.agents.builders import (
            compile_example_graph,  # type: ignore[import-not-found]
        )
        from app.agents.executors import (
            ExampleExecutor,  # type: ignore[import-not-found]
        )

        example_graph = compile_example_graph(
            chat_model=chat_model,
            get_session=get_db,
            storage=storage,
            checkpointer=checkpointer,
        )
        example_executor = ExampleExecutor(example_graph, tracing_enabled=settings.TRACING_ENABLED)
        app.state.example_graph = example_graph
        logger.info("Compiled agent graph with PostgreSQL checkpointer")
    except Exception as exc:  # noqa: BLE001
        # Agent layer not yet present / stubbed — keep the API up.
        logger.warning(
            "Agent layer not wired — agent endpoints will be unavailable until "
            "app/agents/** provides compile_example_graph() / ExampleExecutor",
            error=str(exc),
        )

    app.state.example_executor = example_executor
    app.state.checkpointer_pool = checkpointer_pool
    app.state.kb_provider = kb_provider

    return checkpointer_pool, kb_provider


async def _shutdown_infrastructure(checkpointer_pool: object, kb_provider: object) -> None:
    """Tear down infrastructure in reverse initialization order."""
    try:
        await cleanup_checkpointer_pool(checkpointer_pool)  # type: ignore[arg-type]
        logger.info("Checkpointer connection pool closed")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error closing checkpointer pool", error=str(e))

    if kb_provider is not None:
        try:
            await kb_provider.close()  # type: ignore[attr-defined]
            logger.info("Knowledgebase provider closed")
        except Exception as e:  # noqa: BLE001
            logger.warning("Error closing knowledgebase provider", error=str(e))

    try:
        cleanup_storage_provider()
        logger.info("Storage provider cleaned up")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error cleaning up storage provider", error=str(e))

    try:
        await cleanup_db_engine()
        logger.info("Database engine disposed")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error disposing database engine", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler owning all infrastructure lifecycle."""
    logger.info("Starting %s API...", settings.PROJECT_NAME)

    checkpointer_pool = None
    kb_provider = None

    try:
        checkpointer_pool, kb_provider = await _init_infrastructure(app)
        logger.info("%s API startup complete", settings.PROJECT_NAME)
    except Exception as e:
        logger.error("Failed to start application: %s", str(e), exc_info=True)
        await cleanup_checkpointer_pool(checkpointer_pool)
        raise

    yield

    logger.info("Shutting down %s API...", settings.PROJECT_NAME)
    await _shutdown_infrastructure(checkpointer_pool, kb_provider)
    logger.info("%s API shutdown complete", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)

# Register global exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
logger.info("Registered global exception handlers")

# Middleware
setup_cors(app)

# ============================================================
# Routes
# ============================================================
app.include_router(health.router, prefix=API_V1_PREFIX)

# V2 async task-pattern routers are included here as they are added.


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"{settings.PROJECT_NAME} API", "status": "ok"}
