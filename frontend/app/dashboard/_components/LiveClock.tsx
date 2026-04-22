"use client"

import { useEffect, useState } from "react"

export function LiveClock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  return (
    <p className="font-mono text-sm text-[#7f9383]">
      {now.toLocaleString()}
    </p>
  )
}
