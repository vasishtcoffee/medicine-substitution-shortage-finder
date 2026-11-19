"""FastAPI application: MySQL (authoritative) + MongoDB (feed/events), cookie auth, role-specific DB accounts."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mysql.connector import errors
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse

from . import config, sync
from .errors import mysql_error_handler
from .routers import alerts, auth, dashboard, feed, inventory, medicines, orders, search, syncr


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if config.SYNC_BACKGROUND:
        async def loop():
            while True:
                await asyncio.sleep(config.SYNC_INTERVAL_SECONDS)
                await asyncio.to_thread(sync.run_sync_safe)
        task = asyncio.create_task(loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Medicine Substitution & Shortage Finder",
              description=config.SAFETY_NOTICE, version="1.0.0", lifespan=lifespan)
app.add_exception_handler(errors.Error, mysql_error_handler)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    if exc.status_code == 401:
        response.delete_cookie(config.COOKIE_NAME, path="/", httponly=True,
                               secure=config.COOKIE_SECURE, samesite="lax")
    return response

for r in (auth.router, medicines.router, search.router, inventory.router, alerts.router, orders.router,
          feed.router, syncr.router, dashboard.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "notice": config.SAFETY_NOTICE}
