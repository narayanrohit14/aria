"use client"

import { useEffect, useRef, useState } from "react"

function getWebSocketBaseUrl() {
  const configuredWsUrl = process.env.NEXT_PUBLIC_WS_URL
  if (configuredWsUrl && !configuredWsUrl.includes("localhost")) {
    return configuredWsUrl
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  if (apiUrl && !apiUrl.includes("localhost")) {
    return apiUrl.replace(/^https:/, "wss:").replace(/^http:/, "ws:")
  }

  if (typeof window !== "undefined" && window.location.hostname !== "localhost") {
    return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`
  }

  return "ws://localhost:8000"
}

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

      const WS_URL = getWebSocketBaseUrl()
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
