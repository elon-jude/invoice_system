import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

test_db = Path(__file__).resolve().parents[1] / "backend" / "sandbox-test.db"
test_db.unlink(missing_ok=True)
for suffix in ("-shm", "-wal"):
    Path(str(test_db) + suffix).unlink(missing_ok=True)

os.environ["WASHKING_DB_PATH"] = str(test_db)
os.environ["APP_ENV"] = "test"
os.environ["AUTH_DISABLED"] = "1"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-with-more-than-32-characters"
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient
from backend import auth, database
from backend.auth import create_token, create_user
from backend.main import app
from backend.schemas import InvoiceCreate
from backend.services.invoice_service import create_invoice


def test_health_and_catalog():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        catalog = client.get("/catalog")
        assert catalog.status_code == 200
        assert len(catalog.json()) >= 10


def test_customer_invoice_payment_flow():
    with TestClient(app) as client:
        customer = client.post("/customers", json={
            "name": "Regression Customer",
            "phone": "0240000000",
            "tier": 2,
            "tier_reason": "Can pay an initial deposit",
            "requested_deposit": 1000,
            "first_deposit_amount": 1000,
            "expected_payment_days": 30,
        })
        assert customer.status_code == 201
        cid = customer.json()["id"]

        invoice = client.post("/invoices", json={
            "customer_id": cid,
            "invoice_number": "TEST-INV-0001",
            "total_amount": 5000,
            "initial_deposit": 1000,
            "deposit_method": "cash",
        })
        assert invoice.status_code == 201
        iid = invoice.json()["id"]
        assert invoice.json()["total_paid"] == 1000
        assert invoice.json()["outstanding_balance"] == 4000
        assert invoice.json()["status"] == "PARTIALLY_PAID"

        partial = client.post(f"/invoices/{iid}/payments", json={
            "amount": 2000,
            "payment_method": "mobile money",
            "reference": "PAY-1",
        })
        assert partial.status_code == 201
        assert partial.json()["total_paid"] == 3000
        assert partial.json()["outstanding_balance"] == 2000

        full = client.post(f"/invoices/{iid}/payments", json={"amount": 2000})
        assert full.status_code == 201
        assert full.json()["status"] == "FULLY_PAID"
        assert full.json()["outstanding_balance"] == 0

        overpayment = client.post(f"/invoices/{iid}/payments", json={"amount": 1})
        assert overpayment.status_code == 400


def test_calculator_and_invoice_from_calculation():
    with TestClient(app) as client:
        customer = client.post("/customers", json={
            "name": "Calculator Customer",
            "phone": "0201111111",
            "tier": 3,
            "tier_reason": "Installment customer",
        }).json()

        result = client.post("/calculator/calculate", json={
            "customer_id": customer["id"],
            "facility_type": "single",
            "equipment": [{"code": "basin", "quantity": 2}],
            "additional_cost": 500,
            "discount": 200,
            "amount_paid": 1000,
            "installment_months": 3,
        })
        assert result.status_code == 200
        calc = result.json()
        assert calc["total_cost"] == 5700
        assert calc["net_cost"] == 5500
        assert calc["remaining_balance"] == 4500
        assert calc["installments"]["monthly_amount"] == 1500

        created = client.post("/calculator/invoice", json={
            "customer_id": customer["id"],
            "facility_type": "single",
            "equipment": [{"code": "basin", "quantity": 2}],
            "additional_cost": 500,
            "discount": 200,
            "amount_paid": 1000,
        })
        assert created.status_code == 201
        assert created.json()["total_amount"] == 5500
        assert created.json()["total_paid"] == 1000
        assert created.json()["invoice_number"].startswith("WK-")
        assert len(created.json()["items"]) >= 3


def test_catalog_update_and_duplicate_invoice():
    with TestClient(app) as client:
        item = client.get("/catalog?kind=facility").json()[0]
        updated = client.patch(f"/catalog/{item['id']}", json={"price": 1234.56, "active": True})
        assert updated.status_code == 200
        assert updated.json()["price"] == 1234.56
        assert updated.json()["price_confirmed"] is True

        customer = client.post("/customers", json={"name": "Duplicate Test", "tier": 1}).json()
        payload = {
            "customer_id": customer["id"],
            "invoice_number": "DUPLICATE-INV",
            "total_amount": 100,
        }
        assert client.post("/invoices", json=payload).status_code == 201
        assert client.post("/invoices", json=payload).status_code == 409


def test_protected_endpoints_require_bearer_auth(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    requests = [
        ("GET", "/auth/me", None),
        ("GET", "/auth/users", None),
        ("POST", "/auth/users", {"username": "newstaff", "password": "long-enough-password"}),
        ("POST", "/auth/password/change", {
            "current_password": "current-password", "new_password": "replacement-password",
        }),
        ("POST", "/auth/users/missing/password-reset", {
            "temporary_password": "temporary-password",
        }),
        ("GET", "/dashboard", None),
        ("GET", "/customers", None),
        ("GET", "/customers/me", None),
        ("POST", "/customers", {"name": "Valid Customer", "tier": 1}),
        ("GET", "/customers/missing", None),
        ("PATCH", "/customers/missing", {}),
        ("PATCH", "/customers/missing/tier", {"tier": 1}),
        ("DELETE", "/customers/missing", None),
        ("GET", "/customers/missing/history", None),
        ("GET", "/invoices", None),
        ("GET", "/reports/executive", None),
        ("POST", "/invoices", {"customer_id": "missing", "total_amount": 10}),
        ("GET", "/invoices/missing", None),
        ("GET", "/invoices/missing/history", None),
        ("GET", "/invoices/missing/payments", None),
        ("POST", "/invoices/missing/payments", {"amount": 1}),
        ("GET", "/invoices/payment-submissions", None),
        ("POST", "/invoices/missing/payment-submissions", {"amount": 1}),
        ("POST", "/invoices/payment-submissions/missing/verify", None),
        ("GET", "/reports/revenue", None),
        ("GET", "/expenses", None),
        ("POST", "/expenses", {"category": "Fuel", "description": "Field travel", "amount": 10}),
        ("GET", "/catalog", None),
        ("POST", "/catalog", {"kind": "facility", "name": "Test facility", "price": 1}),
        ("PATCH", "/catalog/missing", {"price": 1}),
        ("POST", "/calculator/calculate", {"facility_type": "single"}),
        ("POST", "/calculator/invoice", {"customer_id": "missing", "facility_type": "single"}),
        ("GET", "/calculator/next-invoice-number", None),
    ]
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
        for method, path, body in requests:
            response = client.request(method, path, json=body)
            assert response.status_code == 401, (method, path, response.status_code, response.text)
        invalid = client.get("/customers", headers={"Authorization": "Bearer not-a-valid-token"})
        assert invalid.status_code == 401


def test_field_officer_is_scoped_and_admin_manages_accounts(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    with database.get_db() as conn:
        field_officer = create_user(conn, "auth_test_field", "field-password-123")
        admin = create_user(conn, "auth_test_admin", "admin-password-123", "administrator")

    with TestClient(app) as client:
        field_headers = {"Authorization": f"Bearer {create_token(field_officer)}"}
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}

        assert client.get("/auth/me", headers=field_headers).json()["role"] == "field_officer"
        created_customer = client.post("/customers", headers=field_headers, json={
            "name": "Field Registration",
            "tier": 2,
        })
        assert created_customer.status_code == 201
        assert client.get("/customers", headers=field_headers).json()[0]["id"] == created_customer.json()["id"]
        assert client.get("/invoices", headers=field_headers).status_code == 200
        assert client.get("/invoices", headers=field_headers).json() == []
        assert client.get("/customers", headers=admin_headers).status_code == 200
        assert client.post("/auth/users", headers=field_headers, json={
            "username": "field_created_user",
            "password": "another-password-123",
        }).status_code == 403

        created = client.post("/auth/users", headers=admin_headers, json={
            "username": "admin_created_user",
            "password": "another-password-123",
            "role": "field_officer",
        })
        assert created.status_code == 201
        assert created.json()["role"] == "field_officer"
        assert created.json()["must_change_password"] is True
        assert any(user["id"] == created.json()["id"] for user in client.get(
            "/auth/users", headers=admin_headers,
        ).json())


def test_ceo_dashboard_is_read_only_and_contains_no_customer_records(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    with database.get_db() as conn:
        ceo = create_user(conn, "auth_test_ceo", "ceo-password-123", "ceo")
        admin = create_user(conn, "ceo_test_admin", "admin-password-123", "administrator")

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {create_token(ceo)}"}
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}
        client.post("/customers", headers=admin_headers, json={"name": "CEO Scope Customer", "tier": 1})
        dashboard = client.get("/dashboard", headers=headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["role"] == "ceo"
        assert dashboard.json()["total_customers"] >= 1
        assert "customer_records" not in dashboard.json()
        assert client.get("/customers", headers=headers).status_code == 403
        assert client.get("/invoices", headers=headers).status_code == 403
        assert client.get("/catalog", headers=headers).status_code == 403
        assert client.get("/auth/users", headers=headers).status_code == 403
        assert client.post("/customers", headers=headers, json={"name": "Forbidden", "tier": 1}).status_code == 403


def test_customer_portal_is_bound_to_one_customer_profile(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    with database.get_db() as conn:
        admin = create_user(conn, "portal_admin", "admin-password-123", "administrator")

    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}
        first = client.post("/customers", headers=admin_headers, json={"name": "Portal Customer One", "tier": 1}).json()
        second = client.post("/customers", headers=admin_headers, json={"name": "Portal Customer Two", "tier": 2}).json()
        first_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": first["id"], "total_amount": 500,
        }).json()
        second_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": second["id"], "total_amount": 800,
        }).json()
        created = client.post("/auth/users", headers=admin_headers, json={
            "username": "portal_customer",
            "password": "customer-password-123",
            "role": "customer",
            "customer_id": first["id"],
        })
        assert created.status_code == 201
        assert created.json()["must_change_password"] is True
        duplicate_profile = client.post("/auth/users", headers=admin_headers, json={
            "username": "second_portal_login",
            "password": "customer-password-123",
            "role": "customer",
            "customer_id": first["id"],
        })
        assert duplicate_profile.status_code == 409
        customer_login = client.post("/auth/login", json={
            "username": "portal_customer",
            "password": "customer-password-123",
        })
        assert customer_login.status_code == 200
        temporary_headers = {"Authorization": f"Bearer {customer_login.json()['access_token']}"}
        changed = client.post("/auth/password/change", headers=temporary_headers, json={
            "current_password": "customer-password-123",
            "new_password": "customer-new-password-123",
        })
        assert changed.status_code == 200
        customer_headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}

        assert client.get("/customers/me", headers=customer_headers).json()["id"] == first["id"]
        invoices = client.get("/invoices", headers=customer_headers).json()
        assert [invoice["id"] for invoice in invoices] == [first_invoice["id"]]
        assert client.get(f"/invoices/{second_invoice['id']}", headers=customer_headers).status_code == 404
        assert client.get(f"/invoices/{second_invoice['id']}/payments", headers=customer_headers).status_code == 404
        assert client.get("/invoices", headers=customer_headers, params={"customer_id": second["id"]}).status_code == 404
        assert client.get("/customers", headers=customer_headers).status_code == 403
        assert client.post(f"/invoices/{first_invoice['id']}/payments", headers=customer_headers, json={
            "amount": 10,
        }).status_code == 403
        assert client.post("/auth/users", headers=customer_headers, json={
            "username": "portal_escalation",
            "password": "customer-password-123",
            "role": "administrator",
        }).status_code == 403


def test_all_roles_can_change_password_and_old_tokens_are_revoked(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "password-change.db")
    monkeypatch.setattr(database, "DIALECT", "sqlite")
    database.init_db()
    with database.get_db() as conn:
        admin = create_user(conn, "password_admin", "starting-password-123", "administrator")

    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}
        profile = client.post("/customers", headers=admin_headers, json={
            "name": "Password Change Customer", "tier": 1,
        }).json()
        with database.get_db() as conn:
            accounts = [
                create_user(conn, "password_ceo", "starting-password-123", "ceo"),
                admin,
                create_user(conn, "password_field", "starting-password-123", "field_officer"),
                create_user(conn, "password_customer", "starting-password-123", "customer", profile["id"]),
            ]

        for account in accounts:
            old_token = create_token(account)
            new_password = f"updated-password-{account['role']}"
            response = client.post("/auth/password/change", headers={
                "Authorization": f"Bearer {old_token}",
            }, json={
                "current_password": "starting-password-123",
                "new_password": new_password,
            })
            assert response.status_code == 200, response.text
            assert response.json()["user"]["must_change_password"] is False
            assert client.get("/auth/me", headers={
                "Authorization": f"Bearer {response.json()['access_token']}",
            }).status_code == 200
            assert client.get("/auth/me", headers={
                "Authorization": f"Bearer {old_token}",
            }).status_code == 401
            assert client.post("/auth/login", json={
                "username": account["username"], "password": new_password,
            }).status_code == 200
            assert client.post("/auth/login", json={
                "username": account["username"], "password": "starting-password-123",
            }).status_code == 401


def test_admin_password_reset_forces_change_and_revokes_existing_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "password-reset.db")
    monkeypatch.setattr(database, "DIALECT", "sqlite")
    database.init_db()
    with database.get_db() as conn:
        admin = create_user(conn, "reset_admin", "admin-password-123", "administrator")
        target = create_user(conn, "reset_field", "field-password-123", "field_officer")
        other = create_user(conn, "reset_ceo", "ceo-password-123", "ceo")

    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}
        target_token = create_token(target)
        reset = client.post(f"/auth/users/{target['id']}/password-reset", headers=admin_headers, json={
            "temporary_password": "temporary-password-123",
        })
        assert reset.status_code == 200
        assert reset.json()["must_change_password"] is True
        assert client.get("/auth/me", headers={
            "Authorization": f"Bearer {target_token}",
        }).status_code == 401
        assert client.post("/auth/login", json={
            "username": "reset_field", "password": "field-password-123",
        }).status_code == 401

        temporary_login = client.post("/auth/login", json={
            "username": "reset_field", "password": "temporary-password-123",
        })
        assert temporary_login.status_code == 200
        temporary_token = temporary_login.json()["access_token"]
        temporary_headers = {"Authorization": f"Bearer {temporary_token}"}
        assert temporary_login.json()["user"]["must_change_password"] is True
        assert client.get("/auth/me", headers=temporary_headers).status_code == 200
        blocked = client.get("/dashboard", headers=temporary_headers)
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "Password change required before continuing"

        change = client.post("/auth/password/change", headers=temporary_headers, json={
            "current_password": "temporary-password-123",
            "new_password": "permanent-password-123",
        })
        assert change.status_code == 200
        assert change.json()["user"]["must_change_password"] is False
        assert client.get("/dashboard", headers={
            "Authorization": f"Bearer {change.json()['access_token']}",
        }).status_code == 200
        assert client.get("/auth/me", headers=temporary_headers).status_code == 401

        assert client.post(f"/auth/users/{admin['id']}/password-reset", headers=admin_headers, json={
            "temporary_password": "temporary-password-123",
        }).status_code == 400
        assert client.post(f"/auth/users/{target['id']}/password-reset", headers={
            "Authorization": f"Bearer {create_token(other)}",
        }, json={"temporary_password": "temporary-password-123"}).status_code == 403


def test_password_change_rejects_wrong_current_and_same_password(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "password-validation.db")
    monkeypatch.setattr(database, "DIALECT", "sqlite")
    database.init_db()
    with database.get_db() as conn:
        user = create_user(conn, "password_validation", "current-password-123", "field_officer")
    headers = {"Authorization": f"Bearer {create_token(user)}"}

    with TestClient(app) as client:
        wrong_password = client.post("/auth/password/change", headers=headers, json={
            "current_password": "incorrect-password",
            "new_password": "replacement-password-123",
        })
        assert wrong_password.status_code == 400
        same_password = client.post("/auth/password/change", headers=headers, json={
            "current_password": "current-password-123",
            "new_password": "current-password-123",
        })
        assert same_password.status_code == 422


def test_field_officers_only_see_customers_they_registered(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    with database.get_db() as conn:
        first_officer = create_user(conn, "field_one", "field-password-123")
        second_officer = create_user(conn, "field_two", "field-password-123")
        admin = create_user(conn, "field_scope_admin", "admin-password-123", "administrator")

    with TestClient(app) as client:
        first_headers = {"Authorization": f"Bearer {create_token(first_officer)}"}
        second_headers = {"Authorization": f"Bearer {create_token(second_officer)}"}
        admin_headers = {"Authorization": f"Bearer {create_token(admin)}"}
        own = client.post("/customers", headers=first_headers, json={"name": "Owned Customer", "tier": 1}).json()
        other = client.post("/customers", headers=second_headers, json={"name": "Other Customer", "tier": 1}).json()
        hidden = client.post("/catalog", headers=admin_headers, json={
            "kind": "equipment",
            "name": "Hidden Field Price",
            "price": 25,
        }).json()
        client.patch(f"/catalog/{hidden['id']}", headers=admin_headers, json={"active": False})

        assert [customer["id"] for customer in client.get("/customers", headers=first_headers).json()] == [own["id"]]
        assert client.get(f"/customers/{other['id']}", headers=first_headers).status_code == 404
        assert client.patch(f"/customers/{own['id']}", headers=first_headers, json={"name": "Changed"}).status_code == 403
        assert client.get("/catalog?include_inactive=true", headers=first_headers).json()
        assert hidden["id"] not in [item["id"] for item in client.get(
            "/catalog?include_inactive=true", headers=first_headers,
        ).json()]
        assert client.post("/calculator/calculate", headers=first_headers, json={
            "customer_id": other["id"],
            "facility_type": "single",
        }).status_code == 404
        assert client.post("/invoices", headers=first_headers, json={
            "customer_id": own["id"],
            "total_amount": 100,
        }).status_code == 403
        assert client.post("/invoices/missing/payments", headers=first_headers, json={
            "amount": 1,
        }).status_code == 403
        assert client.get("/dashboard", headers=first_headers).json() == {
            "role": "field_officer",
            "total_customers": 1,
            "overdue_invoices": 0,
            "overdue_balance": 0,
        }


def test_generated_invoice_numbers_are_unique_and_preview_matches():
    with TestClient(app) as client:
        customer = client.post("/customers", json={"name": "Auto Number Customer", "tier": 1}).json()
        preview = client.get("/calculator/next-invoice-number")
        assert preview.status_code == 200
        number = preview.json()["invoice_number"]
        assert number.startswith("WK-")

        first = client.post("/invoices", json={"customer_id": customer["id"], "total_amount": 100})
        assert first.status_code == 201
        assert first.json()["invoice_number"] == number

        second = client.post("/invoices", json={"customer_id": customer["id"], "total_amount": 100})
        assert second.status_code == 201
        assert second.json()["invoice_number"] != number


def test_concurrent_invoice_number_assignment_is_unique():
    with TestClient(app) as client:
        customer = client.post("/customers", json={"name": "Concurrent Number Customer", "tier": 1}).json()

    def issue_invoice(_):
        with database.get_db() as conn:
            invoice = create_invoice(conn, InvoiceCreate(customer_id=customer["id"], total_amount=100))
            return invoice["invoice_number"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        numbers = list(pool.map(issue_invoice, range(6)))
    assert len(set(numbers)) == 6


def test_legacy_schema_migrates_user_roles_and_price_confirmation(monkeypatch, tmp_path):
    import sqlite3

    legacy_db = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.executescript("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'staff'
            );
            INSERT INTO users VALUES
                ('legacy-user', 'legacy', 'hash', '2020-01-01', 'staff'),
                ('legacy-admin', 'legacy-admin', 'hash', '2020-01-01', 'admin');
            CREATE TABLE catalog_items (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, price NUMERIC(12,2) NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO catalog_items VALUES
                ('legacy-item', 'facility', 'legacy-facility', 'Legacy facility', 100, 1, '2020-01-01', '2020-01-01');
        """)

    monkeypatch.setattr(database, "DB_PATH", legacy_db)
    monkeypatch.setattr(database, "DIALECT", "sqlite")
    database.init_db()

    with database.get_db() as conn:
        user = conn.execute("SELECT role FROM users WHERE id=?", ("legacy-user",)).fetchone()
        admin = conn.execute("SELECT role FROM users WHERE id=?", ("legacy-admin",)).fetchone()
        item = conn.execute("SELECT price_confirmed FROM catalog_items WHERE id=?", ("legacy-item",)).fetchone()
    assert user["role"] == "field_officer"
    assert admin["role"] == "administrator"
    assert item["price_confirmed"] == 0


def _financial_test_accounts(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "financial.db")
    monkeypatch.setattr(database, "DIALECT", "sqlite")
    database.init_db()
    with database.get_db() as conn:
        admin = create_user(conn, "finance_admin", "finance-admin-password", "administrator")
        field = create_user(conn, "finance_field", "finance-field-password", "field_officer")
        other_field = create_user(conn, "finance_other", "finance-other-password", "field_officer")
    headers = lambda user: {"Authorization": f"Bearer {create_token(user)}"}
    return headers(admin), headers(field), headers(other_field), admin, field, other_field


def test_field_payment_submission_requires_admin_verification(monkeypatch, tmp_path):
    admin_headers, field_headers, other_headers, admin, _, _ = _financial_test_accounts(monkeypatch, tmp_path)
    with TestClient(app) as client:
        own_customer = client.post("/customers", headers=field_headers, json={
            "name": "Field Payment Customer", "tier": 1,
        }).json()
        other_customer = client.post("/customers", headers=other_headers, json={
            "name": "Other Officer Customer", "tier": 1,
        }).json()
        own_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": own_customer["id"], "total_amount": 500,
        }).json()
        other_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": other_customer["id"], "total_amount": 200,
        }).json()

        assert [item["id"] for item in client.get("/invoices", headers=field_headers).json()] == [own_invoice["id"]]
        assert client.get(f"/invoices/{other_invoice['id']}", headers=field_headers).status_code == 404
        assert client.post(f"/invoices/{other_invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 50,
        }).status_code == 404

        submitted = client.post(f"/invoices/{own_invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 300, "payment_method": "Cash", "reference": "FIELD-001",
        })
        assert submitted.status_code == 201
        submission = submitted.json()
        assert submission["status"] == "pending"
        assert submission["submitter_username"] == "finance_field"
        assert client.get(f"/invoices/{own_invoice['id']}", headers=admin_headers).json()["total_paid"] == 0
        assert client.get(f"/invoices/{own_invoice['id']}/payments", headers=admin_headers).json() == []
        assert client.get("/invoices/payment-submissions", headers=field_headers).json()[0]["id"] == submission["id"]
        assert client.get("/invoices/payment-submissions", headers=other_headers).json() == []
        assert client.post(f"/invoices/payment-submissions/{submission['id']}/verify", headers=field_headers).status_code == 403

        verified = client.post(f"/invoices/payment-submissions/{submission['id']}/verify", headers=admin_headers)
        assert verified.status_code == 200
        assert verified.json()["submission"]["status"] == "verified"
        assert verified.json()["invoice"]["total_paid"] == 300
        assert verified.json()["invoice"]["outstanding_balance"] == 200
        payment = client.get(f"/invoices/{own_invoice['id']}/payments", headers=admin_headers).json()[0]
        assert payment["recorded_by"] == admin["id"]
        assert client.post(f"/invoices/payment-submissions/{submission['id']}/verify", headers=admin_headers).status_code == 409
        history = client.get(f"/invoices/{own_invoice['id']}/history", headers=admin_headers).json()
        assert any(event["event_type"] == "PAYMENT_SUBMISSION_VERIFIED" for event in history)


def test_payment_rejection_and_failed_verification_are_transactional(monkeypatch, tmp_path):
    admin_headers, field_headers, _, _, _, _ = _financial_test_accounts(monkeypatch, tmp_path)
    with TestClient(app) as client:
        customer = client.post("/customers", headers=field_headers, json={
            "name": "Pending Payment Customer", "tier": 1,
        }).json()
        invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": customer["id"], "total_amount": 100,
        }).json()
        submission = client.post(f"/invoices/{invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 80,
        }).json()
        assert client.post(f"/invoices/{invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 21,
        }).status_code == 400
        recorded = client.post(f"/invoices/{invoice['id']}/payments", headers=admin_headers, json={
            "amount": 30,
        })
        assert recorded.status_code == 201
        assert client.post(f"/invoices/payment-submissions/{submission['id']}/verify", headers=admin_headers).status_code == 400
        pending = client.get("/invoices/payment-submissions", headers=admin_headers).json()
        assert next(row for row in pending if row["id"] == submission["id"])["status"] == "pending"
        assert client.get(f"/invoices/{invoice['id']}", headers=admin_headers).json()["total_paid"] == 30

        rejected = client.post(f"/invoices/payment-submissions/{submission['id']}/reject", headers=admin_headers, json={
            "reason": "Receipt was not provided",
        })
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["decision_note"] == "Receipt was not provided"
        assert client.post(f"/invoices/payment-submissions/{submission['id']}/verify", headers=admin_headers).status_code == 409
        assert client.get(f"/invoices/{invoice['id']}", headers=admin_headers).json()["total_paid"] == 30


def test_revenue_reports_expenses_and_overdue_balances(monkeypatch, tmp_path):
    from datetime import date, timedelta

    admin_headers, field_headers, _, admin, _, _ = _financial_test_accounts(monkeypatch, tmp_path)
    today = date.today()
    yesterday = today - timedelta(days=1)
    with TestClient(app) as client:
        customer = client.post("/customers", headers=field_headers, json={
            "name": "Finance Report Customer", "tier": 1,
        }).json()
        overdue_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": customer["id"],
            "total_amount": 100,
            "due_date": (today - timedelta(days=7)).isoformat(),
        }).json()
        current_invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": customer["id"],
            "total_amount": 200,
            "due_date": (today + timedelta(days=7)).isoformat(),
        }).json()
        for invoice, amount, payment_date in (
            (overdue_invoice, 25, yesterday.isoformat()),
            (current_invoice, 50, today.isoformat()),
        ):
            assert client.post(f"/invoices/{invoice['id']}/payments", headers=admin_headers, json={
                "amount": amount,
                "payment_date": payment_date,
            }).status_code == 201

        pending = client.post(f"/invoices/{overdue_invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 10,
        })
        assert pending.status_code == 201

        for amount, expense_date in ((5, yesterday), (10, today)):
            expense = client.post("/expenses", headers=admin_headers, json={
                "category": "Travel",
                "description": "Customer site visit",
                "amount": amount,
                "expense_date": expense_date.isoformat(),
            })
            assert expense.status_code == 201
            assert expense.json()["recorded_by"] == admin["id"]

        daily = client.get("/reports/revenue", headers=admin_headers, params={
            "period": "daily", "start_date": yesterday.isoformat(), "end_date": today.isoformat(),
        })
        assert daily.status_code == 200
        report = daily.json()
        assert report["total_revenue"] == 75
        assert report["total_expenses"] == 15
        assert report["net_cash"] == 60
        assert report["payment_count"] == 2
        assert report["groups"][0]["revenue"] == 25
        assert report["groups"][1]["revenue"] == 50
        assert report["overdue_invoices"] == 1
        assert report["overdue_balance"] == 75
        assert client.get("/reports/revenue", headers=admin_headers, params={"period": "weekly"}).status_code == 200
        monthly = client.get("/reports/revenue", headers=admin_headers, params={"period": "monthly"})
        assert monthly.status_code == 200
        assert monthly.json()["total_revenue"] == 75
        assert len(monthly.json()["groups"]) == 12
        assert client.get("/expenses", headers=admin_headers).json()
        assert client.post("/expenses", headers=field_headers, json={
            "category": "Fuel", "description": "Unauthorized", "amount": 1,
        }).status_code == 403
        assert client.get("/reports/revenue", headers=field_headers).status_code == 403
        dashboard = client.get("/dashboard", headers=admin_headers).json()
        assert dashboard["overdue_invoices"] == 1
        assert dashboard["overdue_balance"] == 75
        assert dashboard["total_expenses"] == 15
        assert client.get("/reports/revenue", headers=admin_headers, params={
            "period": "daily", "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=367)).isoformat(),
        }).status_code == 422


def test_executive_report_aggregates_revenue_customers_invoices_and_alerts(monkeypatch, tmp_path):
    admin_headers, field_headers, _, _, _, _ = _financial_test_accounts(monkeypatch, tmp_path)
    with database.get_db() as conn:
        ceo = create_user(conn, "executive_report_ceo", "executive-report-password", "ceo")

    with TestClient(app) as client:
        customer = client.post("/customers", headers=field_headers, json={
            "name": "Executive Report Customer", "tier": 2,
        }).json()
        invoice = client.post("/invoices", headers=admin_headers, json={
            "customer_id": customer["id"], "total_amount": 1000, "initial_deposit": 100,
        }).json()
        submission = client.post(f"/invoices/{invoice['id']}/payment-submissions", headers=field_headers, json={
            "amount": 50,
        })
        assert submission.status_code == 201
        expense = client.post("/expenses", headers=admin_headers, json={
            "category": "Transport", "description": "Executive report test", "amount": 25,
        })
        assert expense.status_code == 201

        with database.get_db() as conn:
            conn.execute(
                '''INSERT INTO invoice_items
                   (id,invoice_id,line_no,kind,description,quantity,unit_price,line_total)
                   VALUES(?,?,?,?,?,?,?,?)''',
                ("executive-report-line", invoice["id"], 1, "facility", "Washroom package", 1, 1000, 1000),
            )
            conn.commit()

        report = client.get("/reports/executive", headers={
            "Authorization": f"Bearer {create_token(ceo)}",
        }, params={"period": "monthly"})
        assert report.status_code == 200, report.text
        data = report.json()
        assert data["total_revenue"] == 100
        assert data["total_expenses"] == 25
        assert data["net_cash"] == 75
        assert data["invoices_issued"] == 1
        assert data["invoice_value"] == 1000
        assert sum(group["customers"] for group in data["customer_acquisition"]) == 1
        assert data["top_invoice_lines"] == [{
            "description": "Washroom package",
            "quantity": 1,
            "total": 1000,
        }]
        assert data["pending_payment_submissions"] == 1
        assert client.get("/reports/executive", headers=field_headers).status_code == 403
