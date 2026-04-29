"use client"

import { useEffect, useRef } from "react"

type ARIAOrbProps = {
  isSpeaking?: boolean
  audioStream?: MediaStream | null
  className?: string
}

export function ARIAOrb({
  isSpeaking: speakingOverride,
  audioStream,
  className,
}: ARIAOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvasEl = canvasRef.current
    if (!canvasEl) {
      return
    }

    const context = canvasEl.getContext("2d")
    if (!context) {
      return
    }

    const canvas = canvasEl
    const ctx = context

    let audioLevel = 0
    let rotation = 0
    let internalIsSpeaking = false
    let animationFrameId = 0
    let audioContext: AudioContext | null = null
    let analyser: AnalyserNode | null = null
    let audioData = new Uint8Array(128)

    const IDLE_COL = "rgba(75,184,117,"
    const SPEAK_COL = "rgba(255,80,80,"
    const PARTICLE_COUNT = 440

    const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
      angle: Math.random() * Math.PI * 2,
      radius: 220 + Math.random() * 55,
      speed: Math.random() * 0.0018 + 0.0008,
      size: Math.random() * 1.6 + 0.8,
    }))

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }

    const getSpeakingState = () => speakingOverride ?? internalIsSpeaking

    const readAudio = () => {
      if (!analyser) {
        audioLevel = 0
        internalIsSpeaking = false
        return
      }

      analyser.getByteFrequencyData(audioData)
      let sum = 0
      for (let index = 0; index < audioData.length; index += 1) {
        sum += audioData[index]
      }
      audioLevel = sum / audioData.length / 255
      internalIsSpeaking = audioLevel > 0.05
    }

    function drawHexGrid() {
      const size = 52
      ctx.save()
      ctx.strokeStyle = "rgba(75,184,117,0.045)"
      ctx.lineWidth = 1
      for (let y = 0; y < canvas.height; y += size) {
        for (let x = 0; x < canvas.width; x += size) {
          ctx.beginPath()
          ctx.arc(x, y, size * 0.46, 0, Math.PI * 2)
          ctx.stroke()
        }
      }
      ctx.restore()
    }

    function drawOrb(cx: number, cy: number, size: number) {
      const GREEN = "#4bb875"
      const GREEN_DIM = "rgba(75,184,117,"
      const RED_COL = "rgba(255,90,90,"
      const speaking = getSpeakingState()
      const colBase = speaking ? RED_COL : GREEN_DIM
      const colSolid = speaking ? "#ff5a5a" : GREEN
      const pulse = audioLevel * 18

      ctx.save()
      ctx.translate(cx, cy)

      ctx.beginPath()
      ctx.arc(0, 0, size * 0.46 + pulse * 0.5, 0, Math.PI * 2)
      ctx.strokeStyle = colBase + "0.08)"
      ctx.lineWidth = 18
      ctx.stroke()

      ctx.shadowBlur = 22 + pulse
      ctx.shadowColor = colSolid
      ctx.beginPath()
      ctx.arc(0, 0, size * 0.46, 0, Math.PI * 2)
      ctx.strokeStyle = colBase + "0.55)"
      ctx.lineWidth = 1.5
      ctx.stroke()
      ctx.shadowBlur = 0

      ctx.rotate(rotation * 1.4)
      const SEG = 8
      const ARC_R = size * 0.37
      const GAP_FRAC = 0.18
      for (let i = 0; i < SEG; i += 1) {
        const start = (i / SEG) * Math.PI * 2
        const end = ((i + 1 - GAP_FRAC) / SEG) * Math.PI * 2
        const alpha = 0.25 + (i % 3) * 0.18 + (speaking ? audioLevel * 0.4 : 0)
        ctx.beginPath()
        ctx.arc(0, 0, ARC_R, start, end)
        ctx.strokeStyle = colBase + Math.min(alpha, 0.95) + ")"
        ctx.lineWidth = speaking ? 3.5 : 2.5
        ctx.stroke()
      }

      ctx.rotate(-rotation * 2.6)
      ctx.beginPath()
      ctx.arc(0, 0, size * 0.24, 0, Math.PI * 2)
      ctx.strokeStyle = colBase + "0.28)"
      ctx.lineWidth = 1
      ctx.setLineDash([4, 7])
      ctx.stroke()
      ctx.setLineDash([])

      for (let i = 0; i < 4; i += 1) {
        const angle = (i / 4) * Math.PI * 2
        const radius = size * 0.24
        ctx.beginPath()
        ctx.moveTo(Math.cos(angle) * (radius - 5), Math.sin(angle) * (radius - 5))
        ctx.lineTo(Math.cos(angle) * (radius + 5), Math.sin(angle) * (radius + 5))
        ctx.strokeStyle = colBase + "0.55)"
        ctx.lineWidth = 1.5
        ctx.stroke()
      }

      ctx.shadowBlur = 30 + audioLevel * 40
      ctx.shadowColor = colSolid
      ctx.beginPath()
      ctx.arc(0, 0, 6 + audioLevel * 8, 0, Math.PI * 2)
      ctx.fillStyle = colBase + (0.65 + audioLevel * 0.35) + ")"
      ctx.fill()
      ctx.shadowBlur = 0

      ctx.restore()
    }

    function drawWaveformRing(cx: number, cy: number) {
      const BARS = 52
      const RADIUS = 315
      const speaking = getSpeakingState()
      const color = speaking ? "rgba(255,100,100,0.55)" : "rgba(75,184,117,0.5)"

      for (let i = 0; i < BARS; i += 1) {
        const angle = (i / BARS) * Math.PI * 2
        const bar = (audioData[i] / 255) * 34
        ctx.beginPath()
        ctx.moveTo(cx + Math.cos(angle) * RADIUS, cy + Math.sin(angle) * RADIUS)
        ctx.lineTo(
          cx + Math.cos(angle) * (RADIUS + bar),
          cy + Math.sin(angle) * (RADIUS + bar),
        )
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()
      }
    }

    function drawParticles(cx: number, cy: number) {
      const speaking = getSpeakingState()
      const color = speaking ? SPEAK_COL : IDLE_COL
      ctx.globalCompositeOperation = "lighter"
      for (const particle of particles) {
        particle.angle += particle.speed
        const radius = particle.radius + audioLevel * 110
        const px = cx + Math.cos(particle.angle) * radius
        const py = cy + Math.sin(particle.angle) * radius
        const size = particle.size + audioLevel * 2.8
        ctx.beginPath()
        ctx.arc(px, py, size, 0, Math.PI * 2)
        ctx.fillStyle = color + "0.88)"
        ctx.fill()
      }
      ctx.globalCompositeOperation = "source-over"
    }

    const animate = () => {
      animationFrameId = window.requestAnimationFrame(animate)
      readAudio()
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const cx = canvas.width / 2
      const cy = canvas.height / 2
      rotation += 0.0018

      drawHexGrid()
      drawWaveformRing(cx, cy)
      drawParticles(cx, cy)
      drawOrb(cx, cy, 300)
    }

    const setupAudio = async () => {
      try {
        const stream = audioStream
        if (!stream) {
          return
        }

        audioContext = new window.AudioContext()
        const source = audioContext.createMediaStreamSource(stream)
        analyser = audioContext.createAnalyser()
        analyser.fftSize = 256
        source.connect(analyser)
        audioData = new Uint8Array(analyser.frequencyBinCount)
      } catch (error) {
        console.error("ARIA orb audio analyser unavailable:", error)
      }
    }

    resizeCanvas()
    void setupAudio()
    animate()
    window.addEventListener("resize", resizeCanvas)

    return () => {
      window.removeEventListener("resize", resizeCanvas)
      window.cancelAnimationFrame(animationFrameId)
      if (audioContext) {
        void audioContext.close()
      }
    }
  }, [audioStream, speakingOverride])

  return (
    <canvas
      ref={canvasRef}
      className={className ?? ""}
    />
  )
}
