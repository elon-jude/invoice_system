# WASHKING Invoice Management System

Full-stack invoice application with a static frontend and FastAPI backend.

Customers are assessed on how they can handle the initial deposit and assigned a payment tier (1: upfront, 2: short wait, 3: installments). Invoices are issued against them, every payment is recorded, and the total paid, outstanding balance and status (No payment yet / Partially paid / Fully paid) are recalculated automatically.

Toilet facilities and equipment live in a **price list**, so staff pick items instead of typing amounts. A **payment calculator** works out what a customer still owes and can turn the result straight into an invoice.

## Features

| Area | What it does |
|---|---|
| Dashboard | Role-scoped portfolio totals, verified revenue, expenses, net cash, overdue balances and recent invoices. |
| Customers | Register customers, assign and change payment tiers, view each customer's invoices and payment history. |
| Invoices | Issue and print/save invoices, track balances and history, and print/save receipts for official payments. |
| Payments | Field officers submit payment evidence; an administrator must verify it before it changes balances or revenue. |
| Expenses and reports | Record expenses and review daily, weekly or monthly verified revenue, expenses, net cash and overdue balances. |
| New Invoice | Pick the customer, choose a facility and tick equipment from the price list. The total is calculated automatically (including additional costs and subsidy); the backend assigns a unique invoice number. Typing a total by hand still works for one-off invoices. |
| Payment Calculator | Total cost, less subsidy / discount, less amount already paid. Supports equipment with quantities, a customer picker (shows tier and agreed deposit), an installment plan, an overpayment flag, **Create invoice from this** (pre-fills the standard invoice form), **Copy breakdown** and **Print**. |
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
│   ├── routes/        auth, customers, invoices, dashboard, finance, catalog, calculator
│   └── services/      customers, invoices, history, finance, catalog, calculator
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
| `APP_ENV` | No | Defaults to `production`. The development/test-only `AUTH_DISABLED=1` bypass is ignored in production. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | First run | Creates the first administrator when no users exist yet, or promotes the matching account to administrator. Password must be 8+ characters. |
| `ADMIN_PASSWORD_RESET` | No | Set to `1` temporarily to create the configured admin if missing or replace the password of the matching `ADMIN_USERNAME` account with `ADMIN_PASSWORD` at startup. This revokes existing sessions and requires a password change at next sign-in. Unset it after the reset. Password must be at least 8 characters. |
| `DATABASE_URL` | Yes in production | PostgreSQL connection string, e.g. `postgresql://user:pass@host:5432/db`. If unset, the local SQLite file `backend/invoices.db` is used. |
| `JWT_EXPIRE_MINUTES` | No | Token lifetime, default 720 (12 hours). |
| `AUTH_DISABLED` | No (development/test only) | Set to `1` to skip login for local feature testing. **Every data endpoint becomes open to anyone who can reach the server.** It only works when `APP_ENV=development` or `APP_ENV=test`; production always requires authentication. |

The four roles are `ceo` (company-wide dashboard and financial reporting, read-only), `administrator` (full management and account provisioning), `field_officer` (registers and sees only their own customers; calculator and active price-list access), and `customer` (read-only access to the linked customer profile, invoices and payment history). Existing legacy `staff` accounts migrate to `field_officer`; legacy `admin` accounts migrate to `administrator`. Set `ADMIN_USERNAME` to the intended administrator so startup promotes it. The CEO dashboard summarizes verified revenue, expenses, net cash, customer growth, invoice status, itemized invoice lines and finance alerts using stored WASHKING records.

Administrators can create accounts for any role from **Staff Management** and reset another account's password there. Newly created and reset accounts receive a temporary password and must change it at first sign-in. Share temporary passwords securely. Users in all roles can change their password from the **Change password** section. There is no email recovery: users who forget a password must contact an administrator. Password changes and administrator resets invalidate existing sessions. Customer endpoints enforce the linked profile on the backend, irrespective of frontend visibility.

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Local backend

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_backend.ps1
.\run_backend.ps1
```

For the normal local SQLite setup, skip the Docker and `DATABASE_URL` steps and run `./run_backend.ps1`. The launcher uses SQLite by default, even when a stale `DATABASE_URL` exists in the terminal environment.

API: http://127.0.0.1:8001
Docs: http://127.0.0.1:8001/docs (use **Authorize** and paste a token from `POST /auth/login`)

Tables are created automatically on first startup, including the price list tables. The starter price list is added the first time the backend starts. The SQLite file is intentionally ignored by Git.

### Isolated sandbox

Run both the backend and frontend in an authentication-disabled sandbox database:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_sandbox.ps1 -Reset
```

Open **http://127.0.0.1:8080/index.html?sandbox=1**. The sandbox API runs at `http://127.0.0.1:8001` and uses `backend\sandbox.db`, separate from the normal `backend\invoices.db`. Use `-Reset` to clear the sandbox database before starting.

Run the automated API regression suite with:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q
```

### Trying features without logging in (development only)

Use the isolated sandbox rather than changing the production frontend or database:

```powershell
.\run_sandbox.ps1
```

Open **http://127.0.0.1:8080/index.html?sandbox=1**. The launcher enables `AUTH_DISABLED` only in `APP_ENV=development`, and the frontend points to the local sandbox API. The login screen and production API configuration remain unchanged. Never enable the bypass in production; the backend ignores it outside development/test.

## Testing the API with Postman

Import `postman/WASHKING_Invoice_API.postman_collection.json`, set the collection variables `baseUrl`, `username` and `password`, then run the collection. It logs in, then walks through the spec example: a Tier 2 customer, a GH₵5,000 invoice with a GH₵1,000 initial deposit, payments until the invoice is fully paid, and checks every balance and status along the way.

The collection covers the original customer, invoice and payment flow. It does not include the `/catalog` and `/calculator` endpoints yet.

From the command line:

```powershell
npx newman run postman/WASHKING_Invoice_API.postman_collection.json --env-var "baseUrl=http://127.0.0.1:8001" --env-var "username=admin" --env-var "password=<password>"
```

The collection creates real records, so run it against a local or test database, not production.

Invoice numbers are generated automatically in the `WK-<year>-NNNN` format. A preview is shown in the form, but the backend assigns the final number atomically when the invoice is saved.

## Deployment

### Frontend
Push the repository to GitHub and enable GitHub Pages for the repository root. `index.html` is already at the root. Staff sign in with their username and password; the token is kept in the browser's local storage.

The checked-in frontend requires staff sign-in and calls the WASHKING FastAPI Cloud API by default. The `?sandbox=1` query is only for local feature exploration; it skips the login screen and points at `LOCAL_API`, so the backend must also be started with the isolated development sandbox.

### Backend
This FastAPI Cloud app is configured with `backend/` as its runtime directory. Deploy from the repository root with `uv run --no-sync fastapi deploy --app-id <FASTAPI_CLOUD_APP_ID>` so the `backend` package is included. Its `cloud_app:app` entrypoint adds the repository root to the import path before loading the package-based app.

Before going live, attach a managed PostgreSQL database (such as FastAPI Cloud's Neon or Supabase integration) and set `DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` in the deployment's environment. Do not run production on SQLite: cloud instances can restart or scale independently, so the file is not durable shared storage. Make sure `AUTH_DISABLED` is **not** set.

To reset an existing admin password or create the configured admin if that username is missing, temporarily set `ADMIN_PASSWORD_RESET=1` in the deployment environment and deploy/restart. The app updates or creates the account matching `ADMIN_USERNAME` with `ADMIN_PASSWORD`; it does not expose either value or remove any other users. After verifying login, unset `ADMIN_PASSWORD_RESET` and redeploy so subsequent startups do not repeat the reset.

After deployment, update `API_BASE` in `index.html` if the backend URL changes.

## API

All endpoints except `/`, `/health` and `/auth/login` require an `Authorization: Bearer <token>` header. The development/test auth bypass is ignored in production.

- `GET /health`
- `POST /auth/login`: returns `access_token`
- `GET /auth/me`: current account and role
- `GET /auth/users` and `POST /auth/users`: administrator-only account management; accepted roles are `ceo`, `administrator`, `field_officer` and `customer`. New accounts must change their initial password at first sign-in. Customer accounts must be linked to one customer profile.
- `POST /auth/password/change`: authenticated password change for every role; verifies the current password and invalidates existing sessions.
- `POST /auth/users/{user_id}/password-reset`: administrator-only reset for another account; sets a temporary password, requires a change at next sign-in and invalidates existing sessions.
- `GET /reports/executive`: administrator and CEO aggregate dashboard report with date-grouped revenue, expenses, customer acquisition, invoice totals, itemized invoice lines and pending-verification count.
- `GET /dashboard`: returns role-scoped dashboard totals
- `/customers`: administrators can manage all records; field officers can register and list only customers they created; customers use `GET /customers/me` for their own profile and history.
- `/invoices`: administrators manage all invoices and official payments; field officers read invoices for customers they registered and submit payments for administrator verification; customers read only their own invoices and payments.
- `/catalog` and `/calculator`: administrators and field officers can read prices and calculate; only administrators can change prices or issue invoices.
- `POST /invoices`: administrator-only; invoice number is generated automatically (`WK-<year>-NNNN`); optional `initial_deposit` is recorded as the first payment
- `GET /invoices/{invoice_id}`: includes `items` when the invoice was built from the price list
- `GET /invoices/{invoice_id}/history`: administrator-only invoice history
- `POST /invoices/{invoice_id}/payments`: administrator-only; creates an official payment and updates the invoice balance
- `POST /invoices/{invoice_id}/payment-submissions`: field officer submission for an invoice belonging to one of their customers; remains pending until verified
- `GET /invoices/payment-submissions`: administrator review queue or field officer's own submissions
- `POST /invoices/payment-submissions/{submission_id}/verify` and `/reject`: administrator-only, single-review actions; verification creates the official payment atomically with the decision
- `POST /expenses`: administrator-only expense recording; `GET /expenses` is available to administrators and the CEO
- `GET /reports/revenue?period=daily|weekly|monthly`: administrator/CEO report of official payments, expenses, net cash and overdue balances; defaults to a bounded reporting window
- `GET /calculator/next-invoice-number`: administrator-only preview; final assignment is serialized by the backend

The starter price list (4 facilities, 6 equipment items) is seeded on first startup with unconfirmed estimates. The warning remains until an administrator saves each active item's real price; newly added items are confirmed. Invoices keep the prices they were created with, so later price changes never alter existing invoices. All displayed amounts use GH₵.

Field submissions are not official receipts: only administrator verification inserts an official payment and changes an invoice balance. Verification is atomic and cannot be replayed. Printable invoice and payment receipt views support browser printing and Save as PDF. Revenue reports exclude pending or rejected submissions. Project tracking, role-based notifications beyond in-app overdue alerts, and a cross-system audit log remain planned follow-on phases; field officers cannot issue invoices or record official payments.

Customer deletion is blocked when linked invoices exist. Payments that would exceed the outstanding balance are rejected.