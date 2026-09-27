# WASHKING Invoice Management System

Full-stack invoice application with a static frontend and FastAPI backend.

## Structure

```text
WASHKING_invoice_fullstack/
├── index.html
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── routes/
│   └── services/
├── setup_backend.ps1
├── run_backend.ps1
└── .gitignore
```

## Local backend

```powershell
.\setup_backend.ps1
.\run_backend.ps1
```

API: http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs

The SQLite database is created automatically on first startup. It is intentionally ignored by Git.

## Deployment

### Frontend
Push the repository to GitHub and enable GitHub Pages for the repository root. `index.html` is already at the root.

### Backend
Deploy from the repository root with `uv run fastapi deploy`. The root `pyproject.toml` declares the `backend.main:app` entrypoint and all Cloud dependencies.

For production data, attach a managed PostgreSQL database (such as FastAPI Cloud's Neon or Supabase integration) before going live. The current SQLite file is suitable for local development only; cloud instances can restart or scale independently, so it must not be used as durable shared storage.

After deployment, update `API_BASE` in `index.html` if the backend URL changes.

## API

- `GET /health`
- `GET /dashboard`
- `GET /customers`
- `POST /customers`
- `GET /customers/{customer_id}`
- `PATCH /customers/{customer_id}`
- `PATCH /customers/{customer_id}/tier`
- `DELETE /customers/{customer_id}`
- `GET /customers/{customer_id}/history`
- `GET /invoices`
- `POST /invoices`
- `GET /invoices/{invoice_id}`
- `GET /invoices/{invoice_id}/history`
- `GET /invoices/{invoice_id}/payments`
- `POST /invoices/{invoice_id}/payments`

Customer deletion is blocked when linked invoices exist.
