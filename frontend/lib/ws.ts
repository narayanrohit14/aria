"use client"

import { useEffect, useRef, useState } from "react"

export function useSubtitles(room: string = "default") {
  const [subtitle, setSubtitle] = useState<string>("")
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef(0)
  const unmountedRef = useRef(false)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    unmountedRef.current = false
    reconnectRef.current = 0

    const connect = () => {
      if (unmountedRef.current) {
        return
      }

      const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"
      const ws = new WebSocket(`${WS_URL}/ws/subtitles/${room}`)

      ws.onopen = () => {
        setConnected(true)
        reconnectRef.current = 0
      }

      ws.onclose = () => {
        setConnected(false)
        wsRef.current = null

        if (unmountedRef.current) {
          return
        }

        reconnectRef.current += 1
        reconnectTimerRef.current = setTimeout(() => {
          connect()
        }, 2000)
      }

      ws.onmessage = (event) => {
        if (event.data === "__CLEAR__") {
          setSubtitle("")
        } else {
          setSubtitle(event.data)
        }
      }

      wsRef.current = ws
    }

    connect()

    return () => {
      unmountedRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [room])

  return { subtitle, connected }
}
