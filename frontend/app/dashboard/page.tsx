import Link from "next/link"

import { DTCCLogo } from "@/components/ui/DTCCLogo"
import { MetricCard } from "@/components/ui/MetricCard"
import { RiskBadge } from "@/components/ui/RiskBadge"
import { ariaApi } from "@/lib/api"
import type { DatasetSummary, Finding, FindingListResponse, HealthResponse } from "@/lib/types"

import { FindingsPanel } from "./_components/FindingsPanel"
import { LiveClock } from "./_components/LiveClock"

export const dynamic = "force-dynamic"

const lifecyclePhases = [
  "PLANNING",
  "RISK ASSESSMENT",
  "FIELDWORK",
  "ANALYSIS",
  "REPORTING",
  "FOLLOW-UP",
]

function formatPercent(value?: number | null) {
  if (typeof value !== "number") {
    return "Unavailable"
  }
  return `${(value * 100).toFixed(1)}%`
}

function formatMeanStd(value?: number | null) {
  if (typeof value !== "number") {
    return "Unavailable"
  }
  return `${value.toFixed(2)} ± --`
}

function derivePortfolioRisk(findings: Finding[]) {
  if (findings.some((finding) => finding.risk_level === "HIGH")) {
    return "HIGH"
  }
  if (findings.some((finding) => finding.risk_level === "MEDIUM")) {
    return "MEDIUM"
  }
  if (findings.some((finding) => finding.risk_level === "LOW")) {
    return "LOW"
  }
  return "Unavailable"
}

export default async function DashboardPage() {
  const [health, findingsResponse, datasetSummary] = await Promise.all([
    ariaApi.getHealth().catch(() => null as HealthResponse | null),
    ariaApi
      .getFindings({ limit: 6 })
      .catch(() => ({ findings: [], total: 0 }) as FindingListResponse),
    ariaApi.getDatasetSummary().catch(() => null as DatasetSummary | null),
  ])

  const findings = findingsResponse.findings
  const metrics = health?.model_metrics ?? null
  const portfolioRisk = derivePortfolioRisk(findings)

  return (
    <div className="relative min-h-[calc(100vh-56px)] px-6 py-8">
      <div className="pointer-events-none absolute left-6 top-8 hidden xl:block">
        <DTCCLogo className="h-7 w-auto opacity-70" />
      </div>
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="flex flex-col gap-3 border-b border-[#1a2e1a] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-sm uppercase tracking-[0.24em] text-[#4bb875]">
              ARIA Command Center
            </p>
            <h1 className="mt-2 text-4xl font-semibold text-white sm:text-5xl">
              Risk Intelligence Dashboard
            </h1>
          </div>
          <LiveClock />
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Portfolio Risk Level"
            value={
              portfolioRisk === "Unavailable" ? (
                "Unavailable"
              ) : (
                <span className="inline-flex">
                  <RiskBadge level={portfolioRisk} />
                </span>
              )
            }
            subValue="Derived from current findings stream"
            highlight={portfolioRisk === "HIGH"}
          />
          <MetricCard
            label="Model F1 Score"
            value={metrics ? formatPercent(metrics.cv_f1_mean) : datasetSummary ? "Demo Mode" : "Unavailable"}
            subValue={metrics ? "Cross-validation mean" : "Model artifact pending"}
            trend="up"
          />
          <MetricCard
            label="Fraud Cases Detected"
            value={
              typeof metrics?.n_fraud_cases === "number"
                ? metrics.n_fraud_cases.toLocaleString()
                : typeof datasetSummary?.fraud_cases === "number"
                  ? datasetSummary.fraud_cases.toLocaleString()
                : "Unavailable"
            }
            subValue={datasetSummary ? "Seeded Railway positives" : "Training dataset positives"}
          />
          <MetricCard
            label="Model Confidence"
            value={metrics ? formatPercent(metrics.cv_roc_auc_mean) : datasetSummary ? "API Linked" : "Unavailable"}
            subValue={metrics ? "ROC-AUC performance" : "Railway dataset connected"}
            highlight
          />
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Railway Transactions"
            value={datasetSummary?.transactions.toLocaleString() ?? "Unavailable"}
            subValue="Seeded representative sample"
          />
          <MetricCard
            label="Seeded Users"
            value={datasetSummary?.users.toLocaleString() ?? "Unavailable"}
            subValue="Customer records"
          />
          <MetricCard
            label="Seeded Cards"
            value={datasetSummary?.cards.toLocaleString() ?? "Unavailable"}
            subValue="Payment instruments"
          />
          <MetricCard
            label="Seeded Fraud Rate"
            value={formatPercent(datasetSummary?.fraud_rate)}
            subValue="Label coverage in Railway"
          />
        </section>

        <section className="rounded-2xl border border-[#1a2e1a] bg-[#0d140d] p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold text-white">
                Classifier Performance
              </h2>
              <p className="mt-1 text-sm text-[#8aa08e]">
                Current fraud model stability and discrimination metrics.
              </p>
            </div>
            <Link
              href="/session"
              className="font-mono text-sm text-[#4bb875] hover:text-[#86efac]"
            >
              Open live session →
            </Link>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="F1 Score"
              value={formatMeanStd(metrics?.cv_f1_mean)}
              subValue="Std unavailable from health endpoint"
            />
            <MetricCard
              label="Precision"
              value={formatMeanStd(metrics?.cv_precision_mean)}
              subValue="Std unavailable from health endpoint"
            />
            <MetricCard
              label="Recall"
              value={formatMeanStd(metrics?.cv_recall_mean)}
              subValue="Std unavailable from health endpoint"
            />
            <MetricCard
              label="ROC-AUC"
              value={formatMeanStd(metrics?.cv_roc_auc_mean)}
              subValue="Std unavailable from health endpoint"
            />
          </div>

          <p className="mt-6 font-mono text-sm text-[#8aa08e]">
            {metrics
              ? `Optimal threshold: ${metrics.optimal_threshold.toFixed(2)} | Training samples: ${metrics.n_samples.toLocaleString()} | Fraud cases: ${metrics.n_fraud_cases.toLocaleString()}`
              : "Optimal threshold: Unavailable | Training samples: Unavailable | Fraud cases: Unavailable"}
          </p>
        </section>

        <FindingsPanel findings={findings} />

        <section className="rounded-2xl border border-[#1a2e1a] bg-[#0d140d] p-6">
          <h2 className="text-2xl font-semibold text-white">
            Audit Lifecycle Status
          </h2>
          <p className="mt-1 text-sm text-[#8aa08e]">
            Current workflow emphasis across the internal audit program.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            {lifecyclePhases.map((phase) => {
              const active = phase === "RISK ASSESSMENT"
              return (
                <span
                  key={phase}
                  className={`rounded-full border px-4 py-2 font-mono text-xs uppercase tracking-[0.16em] ${
                    active
                      ? "border-[#4bb875] bg-[#12331c] text-[#86efac]"
                      : "border-[#1a2e1a] bg-[#101710] text-[#6f8273]"
                  }`}
                >
                  {phase}
                </span>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}
