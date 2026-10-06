import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse


async def invalid_operation(
    request: Request, error: Exception
) -> JSONResponse:
    frames = traceback.extract_tb(error.__traceback__)
    if frames:
        frame = frames[-1]
        logging.getLogger("her").warning(
            "Invalid operation: %s at %s:%s",
            type(error).__name__,
            frame.name,
            frame.lineno,
        )
    return JSONResponse({"error": "invalid_operation"}, status_code=400)


async def invalid_request(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse({"error": "invalid_request"}, status_code=422)


async def missing_record(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse({"error": "record_not_found"}, status_code=404)


async def internal_failure(request: Request, error: Exception) -> JSONResponse:
    logging.getLogger("her").error(
        "Internal failure: %s", type(error).__name__
    )
    return JSONResponse({"error": "internal_failure"}, status_code=500)
