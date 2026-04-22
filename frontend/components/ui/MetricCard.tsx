import type { ReactNode } from "react"

type MetricCardProps = {
  label: string
  value: ReactNode
  subValue?: string
  trend?: "up" | "down" | "neutral"
  highlight?: boolean
}

const trendMap = {
  up: { symbol: "↑", className: "text-[#4bb875]" },
  down: { symbol: "↓", className: "text-[#f87171]" },
  neutral: { symbol: "→", className: "text-[#9ca3af]" },
}

export function MetricCard({
  label,
  value,
  subValue,
  trend,
  highlight = false,
}: MetricCardProps) {
  const trendDisplay = trend ? trendMap[trend] : null

  return (
    <div
      className={`rounded-xl border bg-[#0f1a0f] p-4 ${
        highlight
          ? "border-[#4bb875]/60 shadow-[0_0_0_1px_rgba(75,184,117,0.22),0_0_24px_rgba(75,184,117,0.12)]"
          : "border-[#1a2e1a]"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="text-xs uppercase tracking-[0.18em] text-[rgba(75,184,117,0.6)]">
          {label}
        </p>
        {trendDisplay ? (
          <span className={`text-sm font-medium ${trendDisplay.className}`}>
            {trendDisplay.symbol}
          </span>
        ) : null}
      </div>
      <p className="mt-3 font-mono text-3xl text-white">{value}</p>
      {subValue ? <p className="mt-2 text-sm text-[#8aa08e]">{subValue}</p> : null}
    </div>
  )
}
