from uuid import UUID


def _finding_payload():
    return {
        "title": "Insufficient transaction monitoring controls",
        "criteria": "Controls should detect anomalous transaction patterns within 24 hours",
        "condition": "15% of flagged transactions were not reviewed within SLA",
        "cause": "Monitoring thresholds not calibrated to current transaction volumes",
        "consequence": "Increased exposure to undetected fraud and regulatory non-compliance",
        "corrective_action": "Recalibrate monitoring thresholds and implement automated escalation",
        "risk_level": "HIGH",
    }


async def test_create_finding(client):
    response = await client.post("/api/v1/findings/", json=_finding_payload())

    assert response.status_code in (200, 201)
    payload = response.json()
    assert UUID(payload["id"])
    assert payload["risk_level"] == "HIGH"
    assert payload["created_by"] == "ARIA"


async def test_list_findings_empty(client):
    response = await client.get("/api/v1/findings/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["findings"] == []
    assert payload["total"] == 0


async def test_list_findings_after_create(client):
    create_response = await client.post("/api/v1/findings/", json=_finding_payload())
    assert create_response.status_code in (200, 201)

    response = await client.get("/api/v1/findings/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["findings"][0]["title"] == _finding_payload()["title"]


async def test_get_finding_by_id(client):
    create_response = await client.post("/api/v1/findings/", json=_finding_payload())
    finding_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/findings/{finding_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == finding_id
    assert payload["title"] == _finding_payload()["title"]
    assert payload["risk_level"] == "HIGH"


async def test_get_finding_not_found(client):
    response = await client.get("/api/v1/findings/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


async def test_delete_finding(client):
    create_response = await client.post("/api/v1/findings/", json=_finding_payload())
    finding_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/findings/{finding_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/findings/{finding_id}")
    assert get_response.status_code == 404
