type LoadingSpinnerProps = {
  size?: "sm" | "md" | "lg"
  label?: string
}

const sizeClasses = {
  sm: "h-4 w-4 border-2",
  md: "h-8 w-8 border-[3px]",
  lg: "h-12 w-12 border-4",
}

export function LoadingSpinner({
  size = "md",
  label = "Loading...",
}: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 text-center">
      <div
        className={`animate-spin rounded-full border-[#1a2e1a] border-t-[#4bb875] ${sizeClasses[size]}`}
      />
      {label ? <p className="text-sm text-[#8aa08e]">{label}</p> : null}
    </div>
  )
}
