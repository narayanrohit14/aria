"use client"

import { useEffect, useRef, useState } from "react"

import {
  getLocalSubtitleWebSocketFallback,
  httpUrlToWebSocketUrl,
  isProductionRuntime,
  requireAbsoluteHttpUrl,
  requireAbsoluteWebSocketUrl,
} from "@/lib/config"

function getWebSocketBaseUrl() {
  // This is the FastAPI subtitles websocket base, not the LiveKit Cloud URL.
  // LiveKit media connects with the livekit_url returned by /api/v1/sessions.
  const configuredWsUrl = process.env.NEXT_PUBLIC_WS_URL
  const isProduction = isProductionRuntime()
  if (configuredWsUrl) {
    return requireAbsoluteWebSocketUrl(configuredWsUrl, "NEXT_PUBLIC_WS_URL", {
      allowLocalhost: !isProduction,
    })
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  if (apiUrl) {
    const normalizedApiUrl = requireAbsoluteHttpUrl(apiUrl, "NEXT_PUBLIC_API_URL", {
      allowLocalhost: !isProduction,
    })
    return httpUrlToWebSocketUrl(normalizedApiUrl)
  }

  if (isProduction) {
    throw new Error(
      "NEXT_PUBLIC_WS_URL or NEXT_PUBLIC_API_URL is required for production subtitles.",
    )
  }
  return getLocalSubtitleWebSocketFallback()
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

      let WS_URL: string
      try {
        WS_URL = getWebSocketBaseUrl()
      } catch (error) {
        console.error("[ARIA subtitles] websocket configuration error", error)
        setConnected(false)
        return
      }
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
