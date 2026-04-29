"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Room, RoomEvent, Track } from "livekit-client"

import { ARIAOrb } from "@/components/orb/ARIAOrb"
import { DTCCLogo } from "@/components/ui/DTCCLogo"
import { RiskBadge } from "@/components/ui/RiskBadge"
import { ariaApi } from "@/lib/api"
import { useSubtitles } from "@/lib/ws"

const phases = [
  "PLANNING",
  "RISK ASSESSMENT",
  "FIELDWORK",
  "ANALYSIS",
  "REPORTING",
  "FOLLOW-UP",
]

const activePhase = "RISK ASSESSMENT"
const introText =
  "Good afternoon, Aadesh. ARIA is joining the LiveKit audit room now."

function getLiveKitErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown LiveKit error"
}

export default function SessionPage() {
  const [roomName] = useState(() => `aria-aadesh-${Date.now()}`)
  const { subtitle, connected } = useSubtitles(roomName)
  const [localSubtitle, setLocalSubtitle] = useState(introText)
  const [voiceStatus, setVoiceStatus] = useState("CONNECTING")
  const [livekitConnected, setLivekitConnected] = useState(false)
  const [needsGesture, setNeedsGesture] = useState(false)
  const [portfolioRisk, setPortfolioRisk] = useState("UNKNOWN")
  const roomRef = useRef<Room | null>(null)
  const initializedRef = useRef(false)
  const remoteAudioRef = useRef<HTMLDivElement | null>(null)

  const attachRemoteAudio = useCallback((track: Track) => {
    if (track.kind !== Track.Kind.Audio || !remoteAudioRef.current) {
      return
    }
    const element = track.attach()
    element.autoplay = true
    element.dataset.livekitRemoteAudio = "true"
    remoteAudioRef.current.appendChild(element)
  }, [])

  const initializeLiveKit = useCallback(async () => {
    if (initializedRef.current) {
      try {
        await roomRef.current?.startAudio()
        setNeedsGesture(false)
      } catch {
        setNeedsGesture(true)
      }
      return
    }

    initializedRef.current = true
    setVoiceStatus("CREATING ROOM")
    setLocalSubtitle(introText)

    try {
      const session = await ariaApi.createSession(roomName)
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      })

      room
        .on(RoomEvent.Connected, () => {
          setLivekitConnected(true)
          setVoiceStatus("LIVEKIT CONNECTED")
          setLocalSubtitle("LiveKit connected. ARIA is entering the room with the selected Cartesia voice.")
          console.info("[ARIA session] LiveKit connected", { roomName })
        })
        .on(RoomEvent.Disconnected, () => {
          setLivekitConnected(false)
          setVoiceStatus("DISCONNECTED")
          console.warn("[ARIA session] LiveKit disconnected")
        })
        .on(RoomEvent.TrackSubscribed, (track) => {
          console.info("[ARIA session] remote track subscribed", {
            kind: track.kind,
            source: track.source,
          })
          attachRemoteAudio(track)
        })
        .on(RoomEvent.LocalTrackPublished, (publication) => {
          console.info("[ARIA session] local track published", {
            kind: publication.kind,
            source: publication.source,
            trackSid: publication.trackSid,
          })
          if (publication.kind === Track.Kind.Audio) {
            setVoiceStatus("MIC LIVE")
            setLocalSubtitle("Microphone is live. ARIA is listening.")
          }
        })
        .on(RoomEvent.LocalTrackUnpublished, (publication) => {
          console.warn("[ARIA session] local track unpublished", {
            kind: publication.kind,
            source: publication.source,
          })
          if (publication.kind === Track.Kind.Audio) {
            setVoiceStatus("MIC OFF")
            setLocalSubtitle("Microphone is not currently published.")
          }
        })

      roomRef.current = room
      await room.connect(session.livekit_url, session.livekit_token)
      try {
        await room.localParticipant.setMicrophoneEnabled(true)
        const micPublication = room.localParticipant.getTrackPublication(Track.Source.Microphone)
        console.info("[ARIA session] microphone enable requested", {
          isMicrophoneEnabled: room.localParticipant.isMicrophoneEnabled,
          hasPublication: Boolean(micPublication),
          isMuted: micPublication?.isMuted,
        })
      } catch (error) {
        setVoiceStatus("MIC ERROR")
        setLocalSubtitle(`Microphone failed: ${getLiveKitErrorMessage(error)}`)
        throw error
      }

      try {
        await room.startAudio()
        setNeedsGesture(false)
      } catch {
        setNeedsGesture(true)
        setLocalSubtitle("Click anywhere once to allow browser audio playback for ARIA.")
      }

      setVoiceStatus("LISTENING")
    } catch (error) {
      initializedRef.current = false
      setLivekitConnected(false)
      setVoiceStatus("LIVEKIT ERROR")
      setLocalSubtitle(
        error instanceof Error
          ? `LiveKit session failed: ${error.message}`
          : "LiveKit session failed. Check Railway agent and LiveKit credentials.",
      )
    }
  }, [attachRemoteAudio, roomName])

  useEffect(() => {
    void initializeLiveKit()
    return () => {
      roomRef.current?.disconnect()
      roomRef.current = null
    }
  }, [initializeLiveKit])

  useEffect(() => {
    let cancelled = false

    ariaApi
      .getDatasetSummary()
      .then((summary) => {
        if (!cancelled && summary.risk_level) {
          setPortfolioRisk(summary.risk_level)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPortfolioRisk("UNKNOWN")
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const subtitleClasses = useMemo(() => {
    return subtitle || localSubtitle ? "opacity-100" : "opacity-35"
  }, [subtitle, localSubtitle])

  const displaySubtitle = subtitle || localSubtitle

  return (
    <div
      className="relative min-h-screen overflow-hidden bg-[#030a04] text-[#e0ffe8]"
      onClick={() => {
        void initializeLiveKit()
      }}
    >
      <div ref={remoteAudioRef} className="hidden" />
      <div
        className="pointer-events-none absolute inset-0 z-10"
        style={{
          background:
            "repeating-linear-gradient(to bottom, rgba(255,255,255,0.03) 0px, rgba(255,255,255,0.02) 1px, rgba(0,0,0,0) 2px)",
        }}
      />

      <div className="pointer-events-none absolute left-[14px] top-[14px] z-20 h-7 w-7 border-l-2 border-t-2 border-[#4bb875]/55" />
      <div className="pointer-events-none absolute right-[14px] top-[14px] z-20 h-7 w-7 rotate-90 border-l-2 border-t-2 border-[#4bb875]/55" />
      <div className="pointer-events-none absolute bottom-[14px] left-[14px] z-20 h-7 w-7 -rotate-90 border-l-2 border-t-2 border-[#4bb875]/55" />
      <div className="pointer-events-none absolute bottom-[14px] right-[14px] z-20 h-7 w-7 rotate-180 border-l-2 border-t-2 border-[#4bb875]/55" />

      <header className="fixed left-0 right-0 top-0 z-30 flex items-start justify-between px-7 pt-6">
        <div className="leading-none">
          <div className="font-mono text-[28px] tracking-[0.375em] text-[#4bb875] [text-shadow:0_0_18px_rgba(75,184,117,0.9),0_0_40px_rgba(75,184,117,0.55)]">
            A.R.I.A.
          </div>
          <div className="mt-1 font-mono text-[9px] tracking-[0.3em] text-[#e0ffe8]/55">
            AUDIT RISK &amp; INSIGHTS AGENT
          </div>
        </div>

        <div className="flex items-start gap-6">
          <div className="text-right">
            <div className="font-mono text-[9.5px] leading-7 tracking-[0.2em] text-[#4bb875]/60">
              <div>
                <span className="text-[#e0ffe8]/55">STATUS&nbsp;&nbsp;&nbsp;&nbsp;</span>
                <span className="text-[#4bb875]">ONLINE</span>
              </div>
              <div>
                <span className="text-[#e0ffe8]/55">AGENT&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
                <span className="text-[#4bb875]">{livekitConnected ? "LIVE" : "JOINING"}</span>
              </div>
              <div>
                <span className="text-[#e0ffe8]/55">VOICE&nbsp;INTERFACE&nbsp;</span>
                <span className="text-[#4bb875]">{voiceStatus}</span>
              </div>
            </div>
          </div>

          <div className="w-[160px] text-right">
            <DTCCLogo className="ml-auto h-8 w-auto opacity-85 [filter:drop-shadow(0_0_12px_rgba(75,184,117,0.12))]" />
            <div className="mt-1 h-px w-full bg-gradient-to-r from-transparent via-[#4bb875]/70 to-transparent" />
            <div className="mt-2 flex items-center justify-end gap-2 font-mono text-[10px] tracking-[0.16em] text-[#e0ffe8]/55">
              <span className={`h-2 w-2 rounded-full ${connected ? "bg-[#4bb875]" : "bg-[#ff5a5a]"}`} />
              SUBTITLES
            </div>
          </div>
        </div>
      </header>

      <div className="pointer-events-none fixed left-1/2 top-6 z-30 flex -translate-x-1/2 flex-col items-center gap-1">
        <div className="font-mono text-[8px] tracking-[0.4em] text-[#e0ffe8]/55">
          PORTFOLIO RISK
        </div>
        <div className="font-mono text-sm tracking-[0.45em] text-[#4bb875] [text-shadow:0_0_12px_rgba(75,184,117,0.9)]">
          {portfolioRisk}
        </div>
      </div>

      {needsGesture ? (
        <div className="fixed left-1/2 top-[18%] z-40 -translate-x-1/2 rounded-full border border-[#4bb875]/50 bg-[#061006]/90 px-5 py-2 font-mono text-xs uppercase tracking-[0.18em] text-[#86efac] shadow-[0_0_24px_rgba(75,184,117,0.18)]">
          Click once to enable ARIA audio
        </div>
      ) : null}

      <div className="relative z-0 flex min-h-screen flex-col">
        <div className="flex min-h-[70vh] flex-1 items-center justify-center px-8 pt-24">
          <div className="relative h-[70vh] w-full max-w-[1200px]">
            <ARIAOrb
              className="absolute inset-0 h-full w-full"
              isSpeaking={livekitConnected}
            />
          </div>
        </div>

        <div className="pointer-events-none fixed bottom-[60px] left-1/2 z-30 flex min-h-[72px] w-[66%] max-w-5xl -translate-x-1/2 items-center justify-center px-4 text-center">
          <div
            className={`max-w-full font-[var(--font-rajdhani)] text-[20px] font-normal leading-[1.65] tracking-[0.5px] text-white [text-shadow:0_0_16px_rgba(75,184,117,0.9),0_0_36px_rgba(75,184,117,0.55)] transition-opacity duration-300 ${subtitleClasses}`}
          >
            {displaySubtitle || "Awaiting ARIA LiveKit transcript..."}
          </div>
        </div>
      </div>

      <div className="pointer-events-none fixed bottom-12 left-[10%] right-[10%] z-20 h-px bg-[linear-gradient(90deg,transparent_0%,rgba(75,184,117,0.55)_20%,#4bb875_50%,rgba(75,184,117,0.55)_80%,transparent_100%)] opacity-50" />

      <footer className="fixed bottom-7 left-0 right-0 z-30 flex items-end justify-between px-7">
        <div className="font-mono text-[9px] leading-[2.2] tracking-[0.2em] text-[#e0ffe8]/55">
          {phases.map((phase) => {
            const active = phase === activePhase
            return (
              <div
                key={phase}
                className="flex items-center gap-2"
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    active ? "bg-[#4bb875] shadow-[0_0_8px_rgba(75,184,117,0.9)]" : "bg-[#4bb875]/55"
                  }`}
                />
                {phase}
              </div>
            )
          })}
        </div>

        <div className="flex items-center gap-4 font-mono text-[10px] tracking-[0.16em] text-[#e0ffe8]/55">
          <RiskBadge
            level={portfolioRisk}
            size="sm"
          />
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${livekitConnected ? "bg-[#4bb875]" : "bg-[#ff5a5a]"}`} />
            LIVEKIT {livekitConnected ? "CONNECTED" : "CONNECTING"}
          </div>
        </div>
      </footer>
    </div>
  )
}
