import { NextRequest, NextResponse } from 'next/server'

const TRANSLATION_API_URL = process.env.TRANSLATION_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { message, target_lang = 'en', session_id = 'default', assistant_mode = true } = body

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
      }),
      cache: 'no-store',
    })

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
    return NextResponse.json(
      { error: 'Failed to connect to translation service. Make sure the Python backend is running.' },
      { status: 503 }
    )
  }
}