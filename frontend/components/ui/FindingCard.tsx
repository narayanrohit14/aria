"use client"

import { useRouter } from "next/navigation"

import { RiskBadge } from "@/components/ui/RiskBadge"
import type { Finding } from "@/lib/types"

type FindingCardProps = {
  finding: Finding
  onClick?: () => void
}

export function FindingCard({ finding, onClick }: FindingCardProps) {
  const router = useRouter()

  const handleClick = () => {
    onClick?.()
    router.push(`/findings/${finding.id}`)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="w-full rounded-xl border border-[#1a2e1a] bg-[#0f1a0f] p-4 text-left transition-colors hover:border-[#4bb875]/50"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <RiskBadge level={finding.risk_level} size="sm" />
          <h3 className="truncate text-base font-semibold text-white">
            {finding.title}
          </h3>
        </div>
        <span className="shrink-0 font-mono text-xs text-[#7f9383]">
          {new Date(finding.created_at).toLocaleString()}
        </span>
      </div>
      <p className="mt-3 line-clamp-1 text-sm text-[#b6c3b8]">
        {finding.condition}
      </p>
      <div className="mt-4 flex items-center justify-between text-xs">
        <span className="rounded-full border border-[#1a2e1a] px-2 py-1 font-mono text-[#8aa08e]">
          {finding.created_by}
        </span>
        <span className="font-mono text-[#4bb875]">→</span>
      </div>
    </button>
  )
}
