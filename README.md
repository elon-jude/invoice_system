# WASHKING Invoice Management System

Full-stack invoice application with a static frontend and FastAPI backend.

Customers are assessed on how they can handle the initial deposit and assigned a payment tier (1: upfront, 2: short wait, 3: installments). Invoices are issued against them, every payment is recorded, and the total paid, outstanding balance and status (No Payment / Partially Paid / Fully Paid) are recalculated automatically.

Toilet facilities and equipment live in a **price list**, so staff pick items instead of typing amounts. A **payment calculator** works out what a customer still owes and can turn the result straight into an invoice.

## Features

| Area | What it does |
|---|---|
| Dashboard | Customer tiers, invoice statuses, total invoiced / received / outstanding, recent invoices. |
| Customers | Register customers, assign and change payment tiers, view each customer's invoices and payment history. |
| Invoices | Issue invoices, record payments, track balances and a full history of events per invoice. |
| New Invoice | Pick the customer, choose a facility and tick equipment from the price list. The total is calculated automatically (including any subsidy) and the invoice number is suggested. Typing a total by hand still works for one-off invoices. |
| Payment Calculator | Total cost, less subsidy / discount, less amount already paid. Supports equipment with quantities, a customer picker (shows tier and agreed deposit), an installment plan, an overpayment flag, **Create invoice from this**, **Copy breakdown** and **Print**. |
| Price List | Starter prices for 4 facilities and 6 equipment items. Edit prices, hide or show items, and add new ones. |
| Invoice items | Invoices built from the price list save their lines at the prices used, and show them on the invoice detail page. Later price changes never alter existing invoices. |

Brand colors are blue `#0088C8`, orange `#F36F3D` and white. They are defined as CSS variables under `:root` at the top of `index.html`, so they can be changed in one place.

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
│   ├── routes/        auth, customers, invoices, dashboard, catalog, calculator
│   └── services/      customers, invoices, history, catalog, calculator
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
| `AUTH_DISABLED` | No (development only) | Set to `1` to skip login so features can be tried without signing in. **Every endpoint becomes open to anyone who can reach the server.** Never set this in production. Off by default. |

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

Tables are created automatically on first startup, including the price list tables. The starter price list is added the first time the backend starts. The SQLite file is intentionally ignored by Git.

### Trying features without logging in (development only)

To look around the app without signing in, turn auth off on both sides:

1. Start the backend with auth disabled:

   ```powershell
   .\run_backend.ps1 -NoAuth
   # or, running uvicorn directly:
   $env:AUTH_DISABLED = "1"
   uvicorn backend.main:app --reload
   ```

   The backend prints a warning at startup while this is on.

2. In `index.html`, keep `AUTH_FROZEN` set to `true` (near the top of the script). The login screen is skipped, the Sign out button is hidden, and the page talks to `LOCAL_API` (default `http://127.0.0.1:8000`). If your backend runs on another port, such as the `8001` that `run_backend.ps1` uses, change `LOCAL_API` to match.

If the page shows a message that the backend still wants a login, the backend was not started with auth disabled.

To turn auth back on, set `AUTH_FROZEN` to `false` and start the backend without `-NoAuth` / `AUTH_DISABLED`. The login code is untouched.

## Testing the API with Postman

Import `postman/WASHKING_Invoice_API.postman_collection.json`, set the collection variables `baseUrl`, `username` and `password`, then run the collection. It logs in, then walks through the spec example: a Tier 2 customer, a GHS 5,000 invoice with a GHS 1,000 initial deposit, payments until the invoice is fully paid, and checks every balance and status along the way.

The collection covers the original customer, invoice and payment flow. It does not include the `/catalog` and `/calculator` endpoints yet.

From the command line:

```powershell
npx newman run postman/WASHKING_Invoice_API.postman_collection.json --env-var "baseUrl=http://127.0.0.1:8001" --env-var "username=admin" --env-var "password=<password>"
```

The collection creates real records, so run it against a local or test database, not production.

## Deployment

### Frontend
Push the repository to GitHub and enable GitHub Pages for the repository root. `index.html` is already at the root. Staff sign in with their username and password; the token is kept in the browser's local storage.

The checked-in frontend is configured for production: `AUTH_FROZEN` is `false`, so staff must sign in and the page calls the WASHKING FastAPI Cloud API. For local feature exploration only, set it to `true`; that skips the login screen and points at `LOCAL_API`, so the backend must also be started with `AUTH_DISABLED=1`.

### Backend
This FastAPI Cloud app is configured with `backend/` as its runtime directory. Deploy from the repository root with `uv run --no-sync fastapi deploy --app-id <FASTAPI_CLOUD_APP_ID>` so the `backend` package is included. Its `cloud_app:app` entrypoint adds the repository root to the import path before loading the package-based app.

Before going live, attach a managed PostgreSQL database (such as FastAPI Cloud's Neon or Supabase integration) and set `DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` in the deployment's environment. Do not run production on SQLite: cloud instances can restart or scale independently, so the file is not durable shared storage. Make sure `AUTH_DISABLED` is **not** set.

After deployment, update `API_BASE` in `index.html` if the backend URL changes.

## API

All endpoints except `/`, `/health` and `/auth/login` require an `Authorization: Bearer <token>` header (unless `AUTH_DISABLED` is on, for development).

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
- `GET /invoices/{invoice_id}`: includes `items` when the invoice was built from the price list
- `GET /invoices/{invoice_id}/history`
- `GET /invoices/{invoice_id}/payments`
- `POST /invoices/{invoice_id}/payments`
- `GET /catalog`: price list (`kind=facility|equipment`, `include_inactive=true` to include hidden items)
- `POST /catalog`: add a facility or equipment item
- `PATCH /catalog/{item_id}`: change an item's name, price or active flag
- `POST /calculator/calculate`: prices a facility with equipment, subsidy and payments, and returns the balance, any overpayment and an optional installment split (nothing is stored)
- `POST /calculator/invoice`: issues an invoice for the net customer cost from a calculation; the lines are saved on the invoice and "amount paid" becomes the first payment
- `GET /calculator/next-invoice-number`: suggested next `INV-<year>-NNNN` number

The starter price list (4 facilities, 6 equipment items) is seeded on first startup with **estimated** prices. Update them on the Price List page. Invoices keep the prices they were created with, so later price changes never alter existing invoices.

Customer deletion is blocked when linked invoices exist. Payments that would exceed the outstanding balance are rejected.