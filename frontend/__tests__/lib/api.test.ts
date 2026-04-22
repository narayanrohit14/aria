import { ariaApi } from "@/lib/api"

describe("ariaApi", () => {
  beforeEach(() => {
    global.fetch = jest.fn()
  })

  afterEach(() => {
    jest.resetAllMocks()
  })

  test("getHealth calls correct URL", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        version: "0.1.0",
        environment: "test",
        model_loaded: true,
        database_connected: true,
        model_metrics: null,
      }),
    })

    await ariaApi.getHealth()

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    )
  })

  test("getFindings builds query string correctly", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        findings: [],
        total: 0,
      }),
    })

    await ariaApi.getFindings({ risk_level: "HIGH", limit: 10 })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("risk_level=HIGH"),
      expect.any(Object),
    )
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("limit=10"),
      expect.any(Object),
    )
  })

  test("createFinding sends POST with body", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "123",
        title: "Test",
        criteria: "Criteria",
        condition: "Condition",
        cause: "Cause",
        consequence: "Consequence",
        corrective_action: "Action",
        risk_level: "HIGH",
        created_at: "2026-01-01T00:00:00Z",
        created_by: "ARIA",
      }),
    })

    await ariaApi.createFinding({
      title: "Test",
      criteria: "Criteria",
      condition: "Condition",
      cause: "Cause",
      consequence: "Consequence",
      corrective_action: "Action",
      risk_level: "HIGH",
    })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/findings"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"title":"Test"'),
      }),
    )
  })
})
