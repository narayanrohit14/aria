"use client"

import { useEffect, useMemo, useState } from "react"

import { DTCCLogo } from "@/components/ui/DTCCLogo"
import { FindingCard } from "@/components/ui/FindingCard"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ariaApi } from "@/lib/api"
import type { Finding } from "@/lib/types"

const PAGE_SIZE = 12
const riskOptions = ["ALL", "HIGH", "MEDIUM", "LOW"] as const
const sortOptions = ["Most Recent", "Risk Level"] as const
type RiskFilter = (typeof riskOptions)[number]
type SortOption = (typeof sortOptions)[number]

const riskRank: Record<string, number> = {
  HIGH: 0,
  MEDIUM: 1,
  LOW: 2,
}

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("ALL")
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState<SortOption>("Most Recent")
  const [page, setPage] = useState(1)

  useEffect(() => {
    let active = true

    const loadFindings = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await ariaApi.getFindings({ limit: 100 })
        if (!active) {
          return
        }
        setFindings(response.findings)
      } catch (loadError) {
        if (!active) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load findings.")
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadFindings()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    setPage(1)
  }, [riskFilter, search, sortBy])

  const filteredFindings = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()

    const next = findings.filter((finding) => {
      const riskMatches = riskFilter === "ALL" || finding.risk_level === riskFilter
      const searchMatches =
        normalizedSearch.length === 0 || finding.title.toLowerCase().includes(normalizedSearch)
      return riskMatches && searchMatches
    })

    next.sort((left, right) => {
      if (sortBy === "Risk Level") {
        const riskDelta =
          (riskRank[left.risk_level] ?? Number.MAX_SAFE_INTEGER) -
          (riskRank[right.risk_level] ?? Number.MAX_SAFE_INTEGER)
        if (riskDelta !== 0) {
          return riskDelta
        }
      }
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    })

    return next
  }, [findings, riskFilter, search, sortBy])

  const totalPages = Math.max(1, Math.ceil(filteredFindings.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const startIndex = (currentPage - 1) * PAGE_SIZE
  const paginatedFindings = filteredFindings.slice(startIndex, startIndex + PAGE_SIZE)
  const showingStart = filteredFindings.length === 0 ? 0 : startIndex + 1
  const showingEnd = Math.min(startIndex + PAGE_SIZE, filteredFindings.length)

  return (
    <div className="relative min-h-[calc(100vh-56px)] bg-[#0a0f0a] px-6 py-8 text-white">
      <div className="pointer-events-none absolute left-6 top-8 hidden xl:block">
        <DTCCLogo className="h-7 w-auto opacity-70" />
      </div>
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 border-b border-[#1a2e1a] pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-4xl font-semibold text-white">Audit Findings</h1>
            <p className="mt-2 text-sm text-[#8aa08e]">
              Review structured findings generated during the audit workflow.
            </p>
          </div>
          <div className="inline-flex items-center rounded-full border border-[#1a2e1a] bg-[#0f1a0f] px-4 py-2 font-mono text-sm text-[#4bb875]">
            {findings.length} total
          </div>
        </div>

        <div className="mt-6 grid gap-4 rounded-2xl border border-[#1a2e1a] bg-[#0f1a0f] p-4 lg:grid-cols-[auto_1fr_auto] lg:items-center">
          <div className="flex flex-wrap gap-2">
            {riskOptions.map((option) => {
              const active = option === riskFilter
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => setRiskFilter(option)}
                  className={`rounded-full border px-3 py-1.5 font-mono text-xs uppercase tracking-[0.2em] transition-colors ${
                    active
                      ? "border-[#4bb875] bg-[#4bb875]/10 text-[#4bb875]"
                      : "border-[#1a2e1a] text-[#8aa08e] hover:border-[#4bb875]/50 hover:text-white"
                  }`}
                >
                  {option}
                </button>
              )
            })}
          </div>

          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search findings by title"
            className="w-full rounded-xl border border-[#1a2e1a] bg-[#091109] px-4 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-[#6f8373] focus:border-[#4bb875]/60"
          />

          <label className="flex items-center gap-3 text-sm text-[#8aa08e]">
            <span className="font-mono uppercase tracking-[0.2em]">Sort</span>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as SortOption)}
              className="rounded-xl border border-[#1a2e1a] bg-[#091109] px-3 py-2 text-sm text-white outline-none focus:border-[#4bb875]/60"
            >
              {sortOptions.map((option) => (
                <option
                  key={option}
                  value={option}
                >
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <div className="flex min-h-[420px] items-center justify-center">
            <LoadingSpinner
              size="lg"
              label="Loading findings..."
            />
          </div>
        ) : error ? (
          <div className="mt-8 rounded-2xl border border-[#7f1d1d] bg-[#2a1010] px-5 py-4 text-sm text-[#fecaca]">
            {error}
          </div>
        ) : (
          <>
            <div className="mt-8 grid gap-5 md:grid-cols-2">
              {paginatedFindings.length > 0 ? (
                paginatedFindings.map((finding) => (
                  <FindingCard
                    key={finding.id}
                    finding={finding}
                  />
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-[#1a2e1a] bg-[#0f1a0f] px-6 py-14 text-center text-[#8aa08e] md:col-span-2">
                  No findings match your filters
                </div>
              )}
            </div>

            <div className="mt-8 flex flex-col gap-4 border-t border-[#1a2e1a] pt-5 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-[#8aa08e]">
                Showing {showingStart}-{showingEnd} of {filteredFindings.length} findings
              </p>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={currentPage === 1}
                  className="rounded-xl border border-[#1a2e1a] px-4 py-2 text-sm text-white transition-colors hover:border-[#4bb875]/50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="font-mono text-sm text-[#8aa08e]">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  disabled={currentPage >= totalPages}
                  className="rounded-xl border border-[#1a2e1a] px-4 py-2 text-sm text-white transition-colors hover:border-[#4bb875]/50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
