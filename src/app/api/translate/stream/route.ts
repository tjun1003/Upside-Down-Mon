import { NextRequest, NextResponse } from 'next/server'
import { Agent } from 'undici'

const TRANSLATION_API_URL = process.env.TRANSLATION_API_URL || 'http://127.0.0.1:8000'
const streamDispatcher = new Agent({
  bodyTimeout: 0,
  headersTimeout: 0,
  connectTimeout: 30_000,
})

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type StreamingFetchInit = RequestInit & {
  dispatcher?: Agent
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      message,
      target_lang = 'auto',
      session_id = 'default',
      assistant_mode = true,
      independent_langs,
    } = body

    if (!message?.trim()) {
      return NextResponse.json(
        { error: 'Message cannot be empty' },
        { status: 400 }
      )
    }

    const response = await fetch(`${TRANSLATION_API_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id,
        message,
        target_lang,
        assistant_mode,
        independent_langs,
      }),
      cache: 'no-store',
      dispatcher: streamDispatcher,
    } as StreamingFetchInit)

    if (!response.ok || !response.body) {
      const errorText = await response.text()
      return NextResponse.json(
        { error: `Translation service error: ${errorText}` },
        { status: response.status || 503 }
      )
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
      },
    })
  } catch (error) {
    console.error('Translation stream API error:', error)

    const errorText = error instanceof Error ? error.message : String(error)
    if (errorText.includes('UND_ERR_BODY_TIMEOUT') || errorText.includes('Body Timeout')) {
      return NextResponse.json(
        { error: 'Translation stream timed out before data arrived. Please retry.' },
        { status: 504 }
      )
    }

    return NextResponse.json(
      { error: 'Failed to connect to translation service. Make sure the Python backend is running.' },
      { status: 503 }
    )
  }
}