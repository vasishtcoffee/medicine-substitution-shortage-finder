"""FastAPI application: MySQL (authoritative) + MongoDB (feed/events), cookie auth, role-specific DB accounts."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mysql.connector import errors

from . import config, sync
from .errors import mysql_error_handler
from .routers import alerts, auth, dashboard, feed, inventory, medicines, orders, search, sqldemo, syncr


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

for r in (auth.router, medicines.router, search.router, inventory.router, alerts.router, orders.router,
          feed.router, syncr.router, sqldemo.router, dashboard.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "notice": config.SAFETY_NOTICE}
