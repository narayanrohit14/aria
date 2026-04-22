async def test_health_returns_200(client):
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("ok", "degraded")
    assert "version" in payload
    assert "model_loaded" in payload
    assert "database_connected" in payload


async def test_health_has_correct_version(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


async def test_status_returns_environment(client):
    response = await client.get("/api/v1/status")

    assert response.status_code == 200
    assert "environment" in response.json()
