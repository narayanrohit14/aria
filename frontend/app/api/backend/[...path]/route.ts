import { NextRequest } from "next/server"

const BACKEND_BASE =
  process.env.ARIA_API_URL ||
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"

type RouteContext = {
  params: {
    path: string[]
  }
}

async function proxy(request: NextRequest, context: RouteContext) {
  const path = `/${context.params.path.join("/")}`
  const target = new URL(path, BACKEND_BASE)
  target.search = request.nextUrl.search

  const headers = new Headers(request.headers)
  headers.delete("host")

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
    cache: "no-store",
  })

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  })
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context)
}
