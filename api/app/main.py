"""BUZZ Reservations API."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import seed, worker
from .db import Base, engine
from .routers import admin, public, widget
from .security import require_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    seed.seed()
    # serverless: no background thread; jobs run via POST /admin/run-jobs
    if os.environ.get("BUZZ_DISABLE_WORKER") != "1" and not os.environ.get("VERCEL"):
        worker.start_timer(60)
    yield


app = FastAPI(title="BUZZ Reservations API", version="0.1.0", lifespan=lifespan)

# dev CORS: the Angular dev server runs on another port; production serves
# the widget from the same domain and pins origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(widget.router)
app.include_router(admin.router)


@app.post("/admin/run-jobs", dependencies=[Depends(require_admin)], tags=["admin"])
def run_jobs():
    """Manual trigger of background jobs — handy for demo/tests."""
    return worker.run_all()


@app.get("/health")
def health():
    return {"ok": True}
