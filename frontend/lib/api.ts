import type {
  AnalysisResponse,
  DatasetSummary,
  Finding,
  FindingListResponse,
  HealthResponse,
  SessionResponse,
  TransactionFeatures,
} from "@/lib/types"

function getApiBase() {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL
  const serverUrl = process.env.ARIA_API_URL || process.env.API_INTERNAL_URL

  if (typeof window === "undefined") {
    if (serverUrl) {
      return serverUrl
    }
    if (publicUrl && !publicUrl.includes("localhost")) {
      return publicUrl
    }
    return "http://localhost:8000"
  }

  if (publicUrl && !publicUrl.includes("localhost")) {
    return publicUrl
  }
  return "/api/backend"
}

type CreateFindingPayload = Omit<Finding, "id" | "created_at" | "created_by">

class ARIAApiClient {
  private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await globalThis.fetch(`${getApiBase()}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    })
    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${path}`)
    }
    return res.json() as Promise<T>
  }

  async getHealth(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>("/health")
  }

  async getFindings(params?: {
    risk_level?: string
    limit?: number
    offset?: number
  }): Promise<FindingListResponse> {
    const search = new URLSearchParams()
    if (params?.risk_level) {
      search.set("risk_level", params.risk_level)
    }
    if (params?.limit !== undefined) {
      search.set("limit", String(params.limit))
    }
    if (params?.offset !== undefined) {
      search.set("offset", String(params.offset))
    }

    const query = search.toString()
    return this.fetch<FindingListResponse>(
      `/api/v1/findings${query ? `?${query}` : ""}`,
    )
  }

  async getFinding(id: string): Promise<Finding> {
    return this.fetch<Finding>(`/api/v1/findings/${id}`)
  }

  async createFinding(data: CreateFindingPayload): Promise<Finding> {
    return this.fetch<Finding>("/api/v1/findings", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async deleteFinding(id: string): Promise<void> {
    const res = await globalThis.fetch(`${getApiBase()}/api/v1/findings/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    })
    if (res.status === 204) {
      return
    }
    if (!res.ok) {
      throw new Error(`API error ${res.status}: /api/v1/findings/${id}`)
    }
  }

  async analyzeTransaction(
    features: TransactionFeatures,
  ): Promise<AnalysisResponse> {
    return this.fetch<AnalysisResponse>("/api/v1/analyze/transaction", {
      method: "POST",
      body: JSON.stringify(features),
    })
  }

  async createSession(roomName: string): Promise<SessionResponse> {
    return this.fetch<SessionResponse>("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({
        room_name: roomName,
      }),
    })
  }

  async getDatasetSummary(): Promise<DatasetSummary> {
    return this.fetch<DatasetSummary>("/api/v1/data/summary")
  }
}

export const ariaApi = new ARIAApiClient()
