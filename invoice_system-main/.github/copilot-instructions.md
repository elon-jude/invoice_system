# Copilot instructions for WASHKING invoice system

This repository is a full-stack invoice management application. Keep changes aligned with the FastAPI backend and browser-based frontend patterns already in use.

## Repo structure
- `index.html` is the frontend entry point.
- `backend/` contains the FastAPI app and business logic.
- `backend/routes/` defines HTTP APIs.
- `backend/services/` holds validation and invoice balance logic.
- `postman/` contains the API smoke-test collection.

## Backend workflow
- Prefer working through the existing route/service layering.
- Keep invoice and payment validation consistent with current business rules.
- Use environment variables for configuration; do not embed credentials.
- For local development, use the SQLite default or PostgreSQL via Docker when needed.

## Validation
- Run the backend locally before checking API behavior.
- Use the Swagger UI or Postman collection to confirm customer, invoice, and payment operations.
- Re-check balance, outstanding amount, and payment status calculations after any financial logic change.

## Security and deployment
- Never store secrets in code.
- Do not rely on SQLite for production deployments.
- Keep JWT secret configuration and admin bootstrap behavior intact.
