import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  // Streaming-only mode: this non-streaming endpoint is intentionally disabled.
  await request.json().catch(() => null)
  return NextResponse.json(
    { error: 'Non-streaming endpoint is disabled. Use /api/translate/stream.' },
    { status: 410 }
  )
}
