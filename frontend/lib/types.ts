export interface ModelMetrics {
  cv_f1_mean: number
  cv_precision_mean: number
  cv_recall_mean: number
  cv_roc_auc_mean: number
  n_samples: number
  n_fraud_cases: number
  optimal_threshold: number
}

export interface HealthResponse {
  status: string
  version: string
  environment: string
  model_loaded: boolean
  database_connected: boolean
  model_metrics: ModelMetrics | null
}

export interface Finding {
  id: string
  title: string
  criteria: string
  condition: string
  cause: string
  consequence: string
  corrective_action: string
  risk_level: "HIGH" | "MEDIUM" | "LOW"
  created_at: string
  created_by: string
  session_id?: string
}

export interface FindingListResponse {
  findings: Finding[]
  total: number
}

export interface AnalysisResponse {
  fraud_probability: number
  fraud_predicted: boolean
  confidence: string
  threshold_used: number
  risk_score: number
  risk_level: string
  audit_flags: string[]
}

export interface TransactionFeatures {
  amount: number
  hour_of_day?: number
  is_online?: number
  mcc_code?: number
  credit_limit?: number
  amount_to_limit_ratio?: number
  has_chip?: number
  card_age_years?: number
  pin_staleness?: number
  is_prepaid?: number
  credit_score?: number
  debt_to_income?: number
  age?: number
}

export interface SessionResponse {
  session_id: string
  room_name: string
  livekit_token: string
  livekit_url: string
  risk_level: string
}
