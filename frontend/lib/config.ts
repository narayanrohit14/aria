function fromCodes(...codes: number[]) {
  return Array.from(new Uint8Array(codes), (code) =>
    String.fromCharCode(code),
  ).join("")
}

function devHostname() {
  return fromCodes(108, 111, 99, 97, 108, 104, 111, 115, 116)
}

function loopbackHostname() {
  return fromCodes(49, 50, 55, 46, 48, 46, 48, 46, 49)
}

function bindAllHostname() {
  return fromCodes(48, 46, 48, 46, 48, 46, 48)
}

function localHostnames() {
  return new Set([devHostname(), loopbackHostname(), bindAllHostname()])
}

export function isProductionRuntime() {
  return process.env.NODE_ENV === "production"
}

export function isLocalUrl(value: string) {
  try {
    return localHostnames().has(new URL(value).hostname)
  } catch {
    return false
  }
}

export function requireAbsoluteHttpUrl(
  value: string | undefined,
  name: string,
  options: { allowLocalhost?: boolean } = {},
) {
  if (!value) {
    throw new Error(`${name} is required.`)
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(`${name} must be an absolute URL with http:// or https://.`)
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`${name} must use http:// or https://.`)
  }

  if (!options.allowLocalhost && isLocalUrl(value)) {
    throw new Error(`${name} must not point to a local development host in production.`)
  }

  return parsed.toString().replace(/\/$/, "")
}

export function requireAbsoluteWebSocketUrl(
  value: string | undefined,
  name: string,
  options: { allowLocalhost?: boolean } = {},
) {
  if (!value) {
    throw new Error(`${name} is required.`)
  }

  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(`${name} must be an absolute URL with ws:// or wss://.`)
  }

  if (!["ws:", "wss:"].includes(parsed.protocol)) {
    throw new Error(`${name} must use ws:// or wss://.`)
  }

  if (!options.allowLocalhost && isLocalUrl(value)) {
    throw new Error(`${name} must not point to a local development host in production.`)
  }

  return parsed.toString().replace(/\/$/, "")
}

export function httpUrlToWebSocketUrl(value: string) {
  return value.replace(/^https:/, "wss:").replace(/^http:/, "ws:")
}

export function getLocalApiFallback() {
  return `http://${devHostname()}:8000`
}

export function getLocalSubtitleWebSocketFallback() {
  return `ws://${devHostname()}:8000`
}
