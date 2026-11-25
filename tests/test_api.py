import os
from pathlib import Path

test_db = Path(__file__).resolve().parents[1] / "backend" / "sandbox-test.db"
test_db.unlink(missing_ok=True)
for suffix in ("-shm", "-wal"):
    Path(str(test_db) + suffix).unlink(missing_ok=True)

os.environ["WASHKING_DB_PATH"] = str(test_db)
os.environ["AUTH_DISABLED"] = "1"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-with-more-than-32-characters"

from fastapi.testclient import TestClient
from backend.main import app


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
            "invoice_number": "TEST-CALC-0001",
            "facility_type": "single",
            "equipment": [{"code": "basin", "quantity": 2}],
            "additional_cost": 500,
            "discount": 200,
            "amount_paid": 1000,
        })
        assert created.status_code == 201
        assert created.json()["total_amount"] == 5500
        assert created.json()["total_paid"] == 1000
        assert len(created.json()["items"]) >= 3


def test_catalog_update_and_duplicate_invoice():
    with TestClient(app) as client:
        item = client.get("/catalog?kind=facility").json()[0]
        updated = client.patch(f"/catalog/{item['id']}", json={"price": 1234.56, "active": True})
        assert updated.status_code == 200
        assert updated.json()["price"] == 1234.56

        customer = client.post("/customers", json={"name": "Duplicate Test", "tier": 1}).json()
        payload = {
            "customer_id": customer["id"],
            "invoice_number": "DUPLICATE-INV",
            "total_amount": 100,
        }
        assert client.post("/invoices", json=payload).status_code == 201
        assert client.post("/invoices", json=payload).status_code == 409
