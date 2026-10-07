from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import ensure_admin, get_current_user
from .config import APP_TITLE, APP_VERSION
from .database import DIALECT, init_db
from .routes.auth import router as auth_router
from .routes.calculator import router as calculator_router
from .routes.customers import router as customers_router
from .routes.invoices import router as invoices_router
from .routes.dashboard import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_admin()
    yield


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="WASHKING customer tiers, invoices, payments and complete invoice history.",
    lifespan=lifespan,
)

# Auth uses bearer tokens (no cookies), so any origin may call the API but
# every data endpoint still requires a valid token.
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
    return {"status": "ok", "database": DIALECT}


protected = [Depends(get_current_user)]
app.include_router(auth_router)
app.include_router(calculator_router, dependencies=protected)
app.include_router(customers_router, dependencies=protected)
app.include_router(invoices_router, dependencies=protected)
app.include_router(dashboard_router, dependencies=protected)
