"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { ariaApi } from "@/lib/api"

type DeleteFindingButtonProps = {
  findingId: string
}

export function DeleteFindingButton({ findingId }: DeleteFindingButtonProps) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDelete = async () => {
    try {
      setPending(true)
      setError(null)
      await ariaApi.deleteFinding(findingId)
      router.push("/findings")
      router.refresh()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete finding.")
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-3">
      <button
        type="button"
        onClick={() => void handleDelete()}
        disabled={pending}
        className="rounded-xl border border-[#7f1d1d] bg-[#2a1010] px-4 py-2.5 text-sm font-medium text-[#fecaca] transition-colors hover:border-[#f87171] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? "Deleting..." : "Delete Finding"}
      </button>
      {error ? <p className="text-sm text-[#fca5a5]">{error}</p> : null}
    </div>
  )
}
