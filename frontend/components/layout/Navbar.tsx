"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/session", label: "Session" },
  { href: "/findings", label: "Findings" },
]

export function Navbar() {
  const pathname = usePathname()
  const [healthy, setHealthy] = useState(false)
  const hidden = pathname.startsWith("/session")

  useEffect(() => {
    let active = true

    const checkHealth = async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
        const res = await fetch(`${base}/health`)
        if (!active) {
          return
        }
        setHealthy(res.ok)
      } catch {
        if (active) {
          setHealthy(false)
        }
      }
    }

    void checkHealth()

    return () => {
      active = false
    }
  }, [])

  if (hidden) {
    return null
  }

  return (
    <nav className="sticky top-0 z-50 flex h-14 w-full items-center justify-between border-b border-[#1a2e1a] bg-[#0a0f0a]/95 px-6 backdrop-blur">
      <div className="min-w-0">
        <p className="font-mono text-lg text-[#4bb875]">A.R.I.A.</p>
        <p className="text-[11px] uppercase tracking-[0.2em] text-[#7f9383]">
          Audit Risk &amp; Insights Agent
        </p>
      </div>

      <div className="flex items-center gap-6">
        {links.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`)
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`border-b pb-1 text-sm transition-colors ${
                active
                  ? "border-[#4bb875] text-[#4bb875]"
                  : "border-transparent text-[#7f9383] hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          )
        })}
      </div>

      <div className="flex items-center gap-2 text-xs font-mono text-[#7f9383]">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            healthy ? "bg-[#4bb875]" : "bg-[#ef4444]"
          }`}
        />
        API
      </div>
    </nav>
  )
}
