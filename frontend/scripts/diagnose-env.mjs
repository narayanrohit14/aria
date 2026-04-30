#!/usr/bin/env node

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "0.0.0.0"])

function isProduction() {
  return process.env.NODE_ENV === "production"
}

function validateUrl(name, value, protocols, allowLocalhost) {
  if (!value) {
    return { name, passed: false, detail: "missing" }
  }

  let parsed
  try {
    parsed = new URL(value)
  } catch {
    return { name, passed: false, detail: `invalid URL: ${value}` }
  }

  if (!protocols.includes(parsed.protocol)) {
    return {
      name,
      passed: false,
      detail: `expected protocol ${protocols.join(" or ")}`,
    }
  }

  if (!allowLocalhost && LOCAL_HOSTNAMES.has(parsed.hostname)) {
    return { name, passed: false, detail: "localhost is not allowed in production" }
  }

  return { name, passed: true, detail: parsed.toString().replace(/\/$/, "") }
}

const production = isProduction()
const checks = [
  validateUrl(
    "NEXT_PUBLIC_API_URL",
    process.env.NEXT_PUBLIC_API_URL,
    ["http:", "https:"],
    !production,
  ),
  validateUrl(
    "ARIA_API_URL or API_INTERNAL_URL",
    process.env.ARIA_API_URL || process.env.API_INTERNAL_URL,
    ["http:", "https:"],
    !production,
  ),
]

const wsUrl = process.env.NEXT_PUBLIC_WS_URL
if (wsUrl) {
  checks.push(validateUrl("NEXT_PUBLIC_WS_URL", wsUrl, ["ws:", "wss:"], !production))
} else if (process.env.NEXT_PUBLIC_API_URL) {
  checks.push({
    name: "NEXT_PUBLIC_WS_URL",
    passed: true,
    detail: "not set; subtitles websocket will be derived from NEXT_PUBLIC_API_URL",
  })
} else {
  checks.push({
    name: "NEXT_PUBLIC_WS_URL",
    passed: !production,
    detail: production
      ? "missing and cannot be derived without NEXT_PUBLIC_API_URL"
      : "missing; local fallback will use ws://localhost:8000",
  })
}

checks.push({
  name: "NEXT_PUBLIC_LIVEKIT_URL",
  passed: true,
  detail: process.env.NEXT_PUBLIC_LIVEKIT_URL
    ? "optional; LiveKit media still uses URL returned by /api/v1/sessions"
    : "optional; not required because API returns livekit_url",
})

let passed = 0
for (const check of checks) {
  if (check.passed) {
    passed += 1
  }
  console.log(`[${check.passed ? "PASS" : "FAIL"}] ${check.name}: ${check.detail}`)
}
console.log(`${passed}/${checks.length} checks passed`)
process.exit(passed === checks.length ? 0 : 1)
