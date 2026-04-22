import { LoadingSpinner } from "@/components/ui/LoadingSpinner"

export default function Loading() {
  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-6">
      <LoadingSpinner size="lg" label="Loading ARIA..." />
    </div>
  )
}
