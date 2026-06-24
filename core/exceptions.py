"""
Centralized DRF exception handling so every error response has the same
predictable shape, regardless of which app or layer raised it:

    {
        "error": "validation_error",
        "detail": "Availability deadline has passed.",
        "field_errors": {}
    }
"""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_default_exception_handler(exc, context)

    if response is None:
        # Anything DRF doesn't already know how to handle (e.g. an
        # unexpected Python exception bubbling up from a service function).
        logger.exception("Unhandled exception in %s: %s", context.get("view"), exc)
        return Response(
            {
                "error": "server_error",
                "detail": "An unexpected error occurred. Please try again.",
                "field_errors": {},
            },
            status=500,
        )

    field_errors = {}
    detail = response.data

    if isinstance(response.data, dict):
        detail = response.data.get("detail", "Request could not be processed.")
        field_errors = {key: value for key, value in response.data.items() if key != "detail"}
    elif isinstance(response.data, list):
        detail = "; ".join(str(item) for item in response.data)

    response.data = {
        "error": "validation_error" if response.status_code == 400 else "request_error",
        "detail": detail,
        "field_errors": field_errors,
    }
    return response
