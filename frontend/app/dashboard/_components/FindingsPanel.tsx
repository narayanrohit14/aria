"use client"

import Link from "next/link"
import { useState } from "react"

import { FindingCard } from "@/components/ui/FindingCard"
import type { Finding } from "@/lib/types"

type FindingsPanelProps = {
  findings: Finding[]
}

const filters = ["ALL", "HIGH", "MEDIUM", "LOW"] as const

export function FindingsPanel({ findings }: FindingsPanelProps) {
  const [activeFilter, setActiveFilter] =
    useState<(typeof filters)[number]>("ALL")

  const visibleFindings =
    activeFilter === "ALL"
      ? findings
      : findings.filter((finding) => finding.risk_level === activeFilter)

  return (
    <section className="rounded-2xl border border-[#1a2e1a] bg-[#0d140d] p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">
            Recent Audit Findings
          </h2>
          <p className="mt-1 text-sm text-[#8aa08e]">
            Latest observations and remediation themes across the portfolio.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => {
            const active = filter === activeFilter
            return (
              <button
                key={filter}
                type="button"
                onClick={() => setActiveFilter(filter)}
                className={`rounded-full border px-3 py-1 text-xs font-mono uppercase tracking-[0.16em] transition-colors ${
                  active
                    ? "border-[#4bb875] bg-[#12331c] text-[#86efac]"
                    : "border-[#1a2e1a] text-[#7f9383] hover:border-[#4bb875]/40 hover:text-white"
                }`}
              >
                {filter}
              </button>
            )
          })}
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {visibleFindings.length > 0 ? (
          visibleFindings.map((finding) => (
            <FindingCard key={finding.id} finding={finding} />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-[#1a2e1a] p-6 text-sm text-[#8aa08e]">
            No findings available for the selected filter.
          </div>
        )}
      </div>

      <div className="mt-6 flex justify-end">
        <Link
          href="/findings"
          className="font-mono text-sm text-[#4bb875] transition-colors hover:text-[#86efac]"
        >
          View all findings →
        </Link>
      </div>
    </section>
  )
}
