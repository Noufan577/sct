from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.errors import validation_exception_handler, global_exception_handler

FRONTEND_INDEX = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} backend starting in {settings.APP_ENV} mode")
    logger.info("Application initialized")
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Local-first, evidence-backed commitment memory layer for Meetily.",
        lifespan=lifespan
    )
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    from app.api.routes import meetings, db_meetings, db_commitments, timeline, query, transcribe, recap, graph, sync, identities, intel
    app.include_router(meetings.router)
    app.include_router(db_meetings.router)
    app.include_router(db_commitments.router)
    app.include_router(timeline.router)
    app.include_router(query.router)
    app.include_router(transcribe.router)
    app.include_router(recap.router)
    app.include_router(graph.router)
    app.include_router(sync.router)
    app.include_router(identities.router)
    app.include_router(intel.router)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}
        
    return app

app = create_app()
