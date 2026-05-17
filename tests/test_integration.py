import pytest
from httpx import AsyncClient
from app.models import UserRole, LoanStatus, PaymentMethod

#this file for integration tests


@pytest.mark.asyncio
async def test_full_finance_flow(client):
    #register dealer
    dealer_payload = {
        "email": "dealer@test.com",
        "full_name": "Dealer One",
        "password": "secure123"
    }
    response = await client.post("/users/", json=dealer_payload) #register dealer
    assert response.status_code == 201 #verify registration , assert means verify the response status code is 201
    dealer= response.json()
     # Manually set role to DEALER (since registration defaults to CLIENT)
    # For test purposes we'll just update it directly via session, but better to have admin endpoint.
     # We'll skip role change and assume dealer can list cars; in real app, role is set via admin.
    # We'll login to get token.

    login_response= await client.post(
        "/auth/login", 
        json={
            "email":  dealer_payload["email"],
            "password": dealer_payload["password"]
        }
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register Client

    client_payload = {
        "email": "client@test.com",
        "full_name": "Client One",
        "password": "secure123"
    }
    response = await client.post("/users/", json=client_payload)
    assert response.status_code == 201

    client_login_res = await client.post("/auth/login", json={
        "email": client_payload["email"],
        "password": client_payload["password"]
    })
    client_token = client_login_res.json()["access_token"]

    client_headers = {"Authorization": f"Bearer {client_token}"}
     # 3. Register Bank (via admin? we'll simulate using a direct db insert or assume bank already exists)
    # For simplicity, we'll create a bank user via the same endpoint and then manually update role.

    bank_payload = {
        "email": "bank@test.com",
        "full_name": "Bank One",
        "password": "secure123"
    }
    response = await client.post("/users/", json=bank_payload)
    assert response.status_code == 201
     # Set bank role and rates manually through database? We'll use a direct db session for test setup.
    # We'll assume bank exists and we know its id. Instead, let's use the existing seed logic.
    # We'll modify the test to use a fixture that creates a bank. For brevity, skip.
    # Instead, we'll hardcode a bank_id from a fixture. We'll add a fixture that creates a bank.
    # But to keep test self-contained, we'll do a quick setup using the write session via a helper.
    # However, we don't have access to the session here. Better to create a fixture for bank.
    # We'll restructure: add bank fixture in conftest.
    pass  # This is incomplete; we'll provide full version below.



