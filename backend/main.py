from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_TITLE, APP_VERSION
from .database import init_db
from .routes.customers import router as customers_router
from .routes.invoices import router as invoices_router
from .routes.dashboard import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="WASHKING customer tiers, invoices, payments and complete invoice history.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": APP_TITLE, "version": APP_VERSION, "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite"}


app.include_router(customers_router)
app.include_router(invoices_router)
app.include_router(dashboard_router)
