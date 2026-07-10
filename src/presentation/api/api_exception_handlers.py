from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.application.api_conflict_error import ApiConflictError
from src.application.api_not_found_error import ApiNotFoundError
from src.application.api_resource_unavailable_error import ApiResourceUnavailableError
from src.contracts.api.api_error_schema import ApiErrorSchema
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


def register_api_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(ApiNotFoundError, _not_found_error)
    app.add_exception_handler(ApiConflictError, _conflict_error)
    app.add_exception_handler(ApiResourceUnavailableError, _unavailable_error)
    app.add_exception_handler(Exception, _unexpected_error)


async def _validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
    return _safe_response(request, 422, "invalid_request", "Request validation failed")


async def _http_error(request: Request, error: HTTPException) -> JSONResponse:
    messages = {401: ("unauthorized", "Authentication failed"), 403: ("forbidden", "Access denied"), 413: ("payload_too_large", "Request is too large"), 429: ("rate_limited", "Too many requests")}
    code, message = messages.get(error.status_code, ("request_failed", "Request could not be processed"))
    return _safe_response(request, error.status_code, code, message)


async def _not_found_error(request: Request, _: ApiNotFoundError) -> JSONResponse:
    return _safe_response(request, 404, "event_not_found", "Moderation event was not found")


async def _conflict_error(request: Request, _: ApiConflictError) -> JSONResponse:
    return _safe_response(request, 409, "invalid_event_state", "Request conflicts with the moderation event")


async def _unavailable_error(request: Request, _: ApiResourceUnavailableError) -> JSONResponse:
    return _safe_response(request, 503, "dependency_unavailable", "A required service is unavailable")


async def _unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled API error endpoint=%s correlation_id=%s", request.url.path, _correlation_id(request))
    return _safe_response(request, 500, "internal_error", "Internal service error")


def _safe_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    payload = ApiErrorSchema(code=code, message=message, correlation_id=_correlation_id(request))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unknown"))
