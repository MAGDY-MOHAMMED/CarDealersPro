import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_complete_finance_workflow(
    client: AsyncClient,
    dealer_headers: dict,
    client_headers: dict,
    admin_headers: dict,
    client_id: str,
    bank_user,
    car_id: str
):
    # ===== 1. Apply for loan =====
    loan_payload = {
        "client_id": client_id,
        "car_id": car_id,
        "bank_id": str(bank_user.id),
        "down_payment": 100000,
        "tenure_months": 36
    }
    res = await client.post("/finance/applications", json=loan_payload, headers=client_headers)
    assert res.status_code == 201
    loan = res.json()
    app_id = loan["id"]
    assert loan["status"] == "PENDING"
    assert loan["monthly_installment"] > 0

    # ===== 2. Approve loan (by admin or bank) =====
    # الكود الحالي مش بيدقق على صلاحيات لتغيير الحالة، لكننا هنستخدم admin للواقعية
    approve_res = await client.patch(
        f"/finance/applications/{app_id}",
        json={"status": "APPROVED"},
        headers=admin_headers
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # ===== 3. Disburse funds =====
    disburse_payload = {
        "application_id": app_id,
        "amount": loan["loan_amount"],
        "bank_reference": "BANK-REF-001"
    }
    disburse_res = await client.post("/finance/disbursements", json=disburse_payload, headers=admin_headers)
    assert disburse_res.status_code == 201
    disbursement = disburse_res.json()
    assert disbursement["bank_reference"] == "BANK-REF-001"

    # ===== 4. Complete sale (transfer ownership) =====
    complete_res = await client.post(
        f"/finance/applications/{app_id}/complete?bank_reference=BANK-REF-001",
        headers=admin_headers
    )
    assert complete_res.status_code == 200
    transaction = complete_res.json()
    assert transaction["amount"] == loan["loan_amount"] + 100000  # loan + down payment
    assert transaction["method"] == "FINANCE"

    # ===== 5. Generate repayment schedule and pay first installment =====
    # Generate schedule (usually done automatically on approval, but we call it)
    schedule_res = await client.post(f"/finance/applications/{app_id}/schedule", headers=admin_headers)
    assert schedule_res.status_code == 200
    schedules = schedule_res.json()
    assert len(schedules) == 36
    first_schedule = schedules[0]
    assert first_schedule["installment_number"] == 1

    # Pay first installment
    payment_res = await client.post(
        f"/finance/applications/{app_id}/schedule/payment?amount={first_schedule['amount']}&grace_period_days=5",
        headers=client_headers
    )
    assert payment_res.status_code == 200
    payment_summary = payment_res.json()
    assert payment_summary["amount_applied"] == first_schedule["amount"]

    # ===== 6. Verify schedule updated =====
    updated_schedule = await client.get(f"/finance/applications/{app_id}/schedule", headers=client_headers)
    updated = updated_schedule.json()
    assert updated[0]["is_paid"] == True