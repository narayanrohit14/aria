async def test_analyze_low_risk_transaction(client):
    response = await client.post(
        "/api/v1/analyze/transaction",
        json={
            "amount": 50.0,
            "credit_limit": 5000.0,
            "amount_to_limit_ratio": 0.01,
            "has_chip": 1,
            "pin_staleness": 1,
            "credit_score": 780,
            "debt_to_income": 0.3,
            "is_online": 0,
            "hour_of_day": 14,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert 0.0 <= payload["fraud_probability"] <= 1.0
    assert payload["confidence"] in ("high", "medium", "low")
    assert isinstance(payload["audit_flags"], list)


async def test_analyze_high_risk_transaction(client):
    response = await client.post(
        "/api/v1/analyze/transaction",
        json={
            "amount": 4500.0,
            "credit_limit": 5000.0,
            "amount_to_limit_ratio": 3.0,
            "has_chip": 0,
            "pin_staleness": 9,
            "credit_score": 500,
            "debt_to_income": 3.2,
            "is_online": 1,
            "hour_of_day": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["audit_flags"]) >= 2
    assert "NO EMV CHIP" in payload["audit_flags"]
    assert "STALE PIN" in payload["audit_flags"]


async def test_analyze_missing_required_field(client):
    response = await client.post("/api/v1/analyze/transaction", json={})

    assert response.status_code == 422
