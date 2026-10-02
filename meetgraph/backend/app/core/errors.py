from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.logging import logger

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error for {request.url}: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Validation Error"},
    )

async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error for {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )
