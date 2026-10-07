# AGENTS.md

## Project overview
This repository contains the WASHKING invoice management system: a static HTML/JS frontend served from the repository root and a FastAPI backend under `backend/`.

The backend manages customers, invoices, deposits, payment allocations, balances, and payment history. Business rules are important: customer deletion is blocked when linked invoices exist, and payments cannot exceed the outstanding balance.

## Primary commands
Run everything from the repository root.

- Start backend with SQLite default:
  - `./run_backend.ps1`
- Initialize backend dependencies:
  - `./setup_backend.ps1`
- Start backend with PostgreSQL:
  - `docker compose up -d`
  - `$env:DATABASE_URL = "postgresql://washking:washking@127.0.0.1:5432/washking_invoices"`
  - `$env:JWT_SECRET = "<generated-secret>"`
  - `$env:ADMIN_USERNAME = "admin"`
  - `$env:ADMIN_PASSWORD = "<choose-a-password>"`
  - `./run_backend.ps1 -UsePostgres`

## Environment and config
The backend reads configuration from environment variables:

- `JWT_SECRET` required in production
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` used only for first account bootstrap
- `DATABASE_URL` optional for PostgreSQL; otherwise SQLite file is used
- `JWT_EXPIRE_MINUTES` optional token lifetime override

The app defaults to SQLite local storage unless PostgreSQL is explicitly enabled via `-UsePostgres`.

## Key directories
- `backend/` — FastAPI app, auth, database, schemas, routes, and services
- `backend/routes/` — API endpoints such as auth, customers, dashboard, and invoices
- `backend/services/` — business logic for customers, invoices, and history
- `postman/` — API collection for smoke testing
- `index.html` — frontend entry point

## Working conventions
- Prefer preserving the existing FastAPI route/service structure.
- Update business logic in the services layer when adjusting invoice balances or validation rules.
- Keep auth and database setup consistent with existing configuration patterns.
- When adding or changing API behavior, update the Postman collection or docs if relevant.
- Keep API behavior explicit and stateless; use environment-driven configuration rather than hardcoded secrets.

## Validation
There is no dedicated Python test suite in this repository by default. The recommended validation flow is:

1. Start the backend locally.
2. Use the Postman collection in `postman/` or call the Swagger docs at `http://127.0.0.1:8001/docs`.
3. Verify authentication, customer creation, invoice issuance, payments, and balance recalculation flows.
4. Confirm that invalid payments that exceed outstanding balances are rejected.

## Do not do
- Do not switch the app to production SQLite.
- Do not hardcode secrets or database credentials into source files.
- Do not remove the existing invoice balance and status logic unless the change explicitly requires it.
