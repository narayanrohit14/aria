type RiskBadgeProps = {
  level: "HIGH" | "MEDIUM" | "LOW" | string
  size?: "sm" | "md"
}

const sizeClasses = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-3 py-1 text-sm",
}

const toneClasses: Record<string, string> = {
  HIGH: "bg-[#7f1d1d] text-[#fca5a5]",
  MEDIUM: "bg-[#78350f] text-[#fcd34d]",
  LOW: "bg-[#14532d] text-[#86efac]",
}

export function RiskBadge({ level, size = "md" }: RiskBadgeProps) {
  const normalized = level.toUpperCase()
  const tone = toneClasses[normalized] ?? "bg-[#1f2937] text-[#d1d5db]"

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono uppercase tracking-wide ${sizeClasses[size]} ${tone}`}
    >
      {normalized}
    </span>
  )
}
