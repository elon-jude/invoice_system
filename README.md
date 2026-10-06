# WASHKING Invoice Management System

Full-stack invoice application with a static frontend and FastAPI backend.

Customers are assessed on how they can handle the initial deposit and assigned a payment tier (1: upfront, 2: short wait, 3: installments). Invoices are issued against them, every payment is recorded, and the total paid, outstanding balance and status (No Payment / Partially Paid / Fully Paid) are recalculated automatically.

## Stack

| Component | Technology |
|---|---|
| Backend | Python + FastAPI |
| Database | PostgreSQL (SQLite fallback for quick local runs) |
| Authentication | JWT bearer tokens |
| API testing | Postman collection in `postman/` |
| Frontend | HTML + CSS + JavaScript (`index.html`) |

## Structure

```text
WASHKING_invoice_fullstack/
├── index.html
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── routes/
│   └── services/
├── postman/
│   └── WASHKING_Invoice_API.postman_collection.json
├── docker-compose.yml
├── setup_backend.ps1
├── run_backend.ps1
└── .gitignore
```

## Configuration

The backend reads these environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `JWT_SECRET` | Yes in production | Long random value used to sign login tokens. If unset, a random one is generated per process and everyone is signed out on restart. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | First run | Creates the first staff account when no users exist yet. Password must be 8+ characters. Ignored once a user exists. |
| `DATABASE_URL` | Yes in production | PostgreSQL connection string, e.g. `postgresql://user:pass@host:5432/db`. If unset, the local SQLite file `backend/invoices.db` is used. |
| `JWT_EXPIRE_MINUTES` | No | Token lifetime, default 720 (12 hours). |

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Local backend

```powershell
.\setup_backend.ps1

# Optional: run PostgreSQL locally instead of SQLite
docker compose up -d
$env:DATABASE_URL = "postgresql://washking:washking@127.0.0.1:5432/washking_invoices"

$env:JWT_SECRET = "<generated secret>"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "<choose a password>"
.\run_backend.ps1 -UsePostgres
```

For the normal local SQLite setup, skip the Docker and `DATABASE_URL` steps and run `./run_backend.ps1`. The launcher uses SQLite by default, even when a stale `DATABASE_URL` exists in the terminal environment.

API: http://127.0.0.1:8001
Docs: http://127.0.0.1:8001/docs (use **Authorize** and paste a token from `POST /auth/login`)

Tables are created automatically on first startup. The SQLite file is intentionally ignored by Git.

## Testing the API with Postman

Import `postman/WASHKING_Invoice_API.postman_collection.json`, set the collection variables `baseUrl`, `username` and `password`, then run the collection. It logs in, then walks through the spec example: a Tier 2 customer, a GHS 5,000 invoice with a GHS 1,000 initial deposit, payments until the invoice is fully paid, and checks every balance and status along the way.

From the command line:

```powershell
npx newman run postman/WASHKING_Invoice_API.postman_collection.json --env-var "baseUrl=http://127.0.0.1:8001" --env-var "username=admin" --env-var "password=<password>"
```

The collection creates real records, so run it against a local or test database, not production.

## Deployment

### Frontend
Push the repository to GitHub and enable GitHub Pages for the repository root. `index.html` is already at the root. Staff sign in with their username and password; the token is kept in the browser's local storage.

### Backend
Deploy from the repository root with `uv run fastapi deploy`. The root `pyproject.toml` declares the `backend.main:app` entrypoint and all Cloud dependencies.

Before going live, attach a managed PostgreSQL database (such as FastAPI Cloud's Neon or Supabase integration) and set `DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` in the deployment's environment. Do not run production on SQLite: cloud instances can restart or scale independently, so the file is not durable shared storage.

After deployment, update `API_BASE` in `index.html` if the backend URL changes.

## API

All endpoints except `/`, `/health` and `/auth/login` require an `Authorization: Bearer <token>` header.

- `GET /health`
- `POST /auth/login`: returns `access_token`
- `GET /auth/me`
- `POST /auth/users`: add a staff account
- `GET /dashboard`
- `GET /customers`
- `POST /customers`
- `GET /customers/{customer_id}`: customer view with invoices, balances and payment history
- `PATCH /customers/{customer_id}`
- `PATCH /customers/{customer_id}/tier`
- `DELETE /customers/{customer_id}`
- `GET /customers/{customer_id}/history`
- `GET /invoices`
- `POST /invoices`: optional `initial_deposit` is recorded as the first payment
- `GET /invoices/{invoice_id}`
- `GET /invoices/{invoice_id}/history`
- `GET /invoices/{invoice_id}/payments`
- `POST /invoices/{invoice_id}/payments`

Customer deletion is blocked when linked invoices exist. Payments that would exceed the outstanding balance are rejected.
