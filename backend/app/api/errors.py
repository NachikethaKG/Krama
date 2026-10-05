"""Every error response uses the contract shape {"error": {code, message, details}} (docs/api-contract.md)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts_gen.common_schema import ApiError, ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)

# Shown in openapi.json for every route, instead of FastAPI's default HTTPValidationError.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal error"},
}

# HTTP status → contract error code, for errors raised by FastAPI/Starlette itself (e.g. unknown route).
_STATUS_CODES: dict[int, ErrorCode] = {
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class ApiException(Exception):
    """Raise from route or service code to return a contract error."""

    def __init__(
        self, status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code: ErrorCode = code
        self.message = message
        self.details = details


def _response(
    status_code: int, code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ApiError(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body, exclude_none=True))


async def _api_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiException)
    return _response(exc.status_code, exc.code, exc.message, exc.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _response(422, "validation_error", "Invalid request", {"fields": fields})


async def _http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "internal" if exc.status_code >= 500 else "validation_error")
    return _response(exc.status_code, code, str(exc.detail))


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return _response(500, "internal", "Internal error")  # never leak details of unexpected errors


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiException, _api_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(Exception, _unhandled)
