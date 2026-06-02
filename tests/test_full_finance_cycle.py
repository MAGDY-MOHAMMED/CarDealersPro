import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_finance_cycle(
    client: AsyncClient,
    dealer_headers: dict,
    client_headers: dict,
    admin_headers: dict,
    client_user,
    bank_user,
    car_id: str
):
    # ---- Apply for loan ----
    loan_payload = {
        "client_id": str(client_user.id),
        "car_id": car_id,
        "bank_id": str(bank_user.id),
        "down_payment": 100_000,
        "tenure_months": 36
    }
    res = await client.post("/finance/applications", json=loan_payload, headers=client_headers)
    assert res.status_code == 201 # 201 Created
    loan = res.json() # get the loan application data
    app_id = loan["id"] # get the loan application id
    assert loan["status"] == "PENDING"
    assert loan["monthly_installment"] > 0

    # ---- Approve loan ----
    approve_res = await client.patch(
        f"/finance/applications/{app_id}",
        json={"status": "APPROVED"},
        headers=admin_headers
    )
    assert approve_res.status_code == 200 # 200 is for updating and 201 is for creating
    assert approve_res.json()["status"] == "APPROVED"

    # ---- Complete sale ----
    complete_res = await client.post(
        f"/finance/applications/{app_id}/complete?bank_reference=REF-001",
        headers=admin_headers
    )
    assert complete_res.status_code == 200
    transaction = complete_res.json()
    expected_total = loan["loan_amount"] + 100_000
    assert transaction["amount"] == pytest.approx(expected_total, rel=0.01)
    assert transaction["method"] == "FINANCE"

    # ---- Generate repayment schedule ----
    schedule_res = await client.post(
        f"/finance/applications/{app_id}/schedule",
        headers=admin_headers
    )
    assert schedule_res.status_code == 200
    schedules = schedule_res.json()
    assert len(schedules) == 36
    first_schedule = schedules[0]
    assert first_schedule["installment_number"] == 1

    # ---- Pay first installment ----
    installment_amount = first_schedule["amount"]          # القيمة كما يخزنها النظام
    payment_res = await client.post(
        f"/finance/applications/{app_id}/schedule/payment"
        f"?amount={installment_amount}&grace_period_days=5",
        headers=client_headers
    )
    assert payment_res.status_code == 200
    payment_summary = payment_res.json()
    # مقارنة مرنة (تسامح 0.01) لتجنب اختلافات التمثيل العشري
    assert payment_summary["amount_applied"] == pytest.approx(installment_amount, rel=0.01)

    # ---- Verify schedule updated ----
    updated_schedule = await client.get(
        f"/finance/applications/{app_id}/schedule",
        headers=client_headers
    )
    updated = updated_schedule.json()
    assert updated[0]["is_paid"] is True 



# =============================================================================
# Validation Errors
# =============================================================================
@pytest.mark.asyncio
async def test_finance_validation_errors(
    client: AsyncClient,
    dealer_headers: dict,
    client_headers: dict,
    admin_headers: dict,
    client_user,
    bank_user,
    car_id: str
):
    # 1. Down payment greater than car price
    bad_loan = {
        "client_id": str(client_user.id),
        "car_id": car_id,
        "bank_id": str(bank_user.id),
        "down_payment": 600_000,  # العربية سعرها 500_000
        "tenure_months": 36
    }
    res = await client.post("/finance/applications", json=bad_loan, headers=client_headers)
    assert res.status_code == 422 
    # 2. Tenure months = 0
    bad_loan["down_payment"] = 100_000
    bad_loan["tenure_months"] = 0
    res = await client.post("/finance/applications", json=bad_loan, headers=client_headers)
    assert res.status_code == 422

    # 3. Invalid car_id
    bad_loan["tenure_months"] = 36
    bad_loan["car_id"] = "00000000-0000-0000-0000-000000000000" # Invalid UUID 
    res = await client.post("/finance/applications", json=bad_loan, headers=client_headers)
    assert res.status_code == 404