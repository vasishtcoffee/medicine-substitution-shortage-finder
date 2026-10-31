"""Translate MySQL errors (custom 454xx errnos raised by stored routines, constraint errors) into HTTP errors."""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from mysql.connector import errors

_STATUS = {45401: 401, 45403: 403, 45404: 404, 45409: 409, 45422: 422}
# 3819 CHECK violated, 1062 duplicate key, 1451/1452 FK, 1048 NOT NULL, 1265/1366 bad value
_CONSTRAINT = {3819, 1062, 1451, 1452, 1048, 1264, 1265, 1366, 1406}


def mysql_error_to_http(e: errors.Error) -> HTTPException:
    errno = getattr(e, "errno", None)
    if errno in _STATUS:
        return HTTPException(_STATUS[errno], e.msg)
    if errno in _CONSTRAINT:
        return HTTPException(409, f"Database constraint violated: {e.msg}")
    if errno in (1213, 1205):
        return HTTPException(409, "Database is busy, please retry")
    return HTTPException(500, "Database error")


async def mysql_error_handler(request: Request, exc: errors.Error):
    he = mysql_error_to_http(exc)
    return JSONResponse({"detail": he.detail}, status_code=he.status_code)
