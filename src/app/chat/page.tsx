'use client'
import React, { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Message {
	id: number
	role: 'user' | 'ai'
	text: string
	timestamp: string
}

const QUICK_PROMPTS = [
	{ label: '🏥 Hospital subsidy', text: 'How do I apply for a hospital subsidy?' },
	{ label: '🎓 Scholarship info', text: 'What scholarships are available for my child?' },
	{ label: '🏠 Housing aid', text: 'How can I apply for affordable housing assistance?' },
	{ label: '⚖️ Legal rights', text: 'What are my rights as a migrant worker?' },
]

const LANG_OPTIONS = [
    { code: 'auto', label: 'Follow input language' },
	{ code: 'en', label: 'English' },
	{ code: 'ms', label: 'Bahasa Melayu' },
	{ code: 'th', label: 'ภาษาไทย' },
	{ code: 'vi', label: 'Tiếng Việt' },
	{ code: 'zh', label: '中文' },
	{ code: 'ta', label: 'தமிழ்' },
]

async function streamAIResponse(
	message: string,
	targetLang: string,
	sessionId: string,
	onToken: (token: string) => void,
): Promise<void> {
	const processEventChunk = (eventChunk: string) => {
		const lines = eventChunk.split(/\r?\n/)
		for (const line of lines) {
			const match = line.match(/^data:\s?(.*)$/)
			if (!match) continue
			const payload = match[1]
			if (!payload) continue

			try {
				const event = JSON.parse(payload)
				if (event?.type === 'token' && typeof event.text === 'string') {
					onToken(event.text)
				}
			} catch {
				// Ignore malformed SSE chunks and keep streaming.
			}
		}
	}

	const response = await fetch('/api/translate/stream', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			session_id: sessionId,
			message,
			target_lang: targetLang,
			assistant_mode: true,
		}),
	})

	if (!response.ok) {
		const body = await response.json().catch(() => ({}))
		const detail = body?.error || 'Backend request failed'
		throw new Error(detail)
	}

	if (!response.body) {
		throw new Error('Streaming response body is empty')
	}

	const reader = response.body.getReader()
	const decoder = new TextDecoder('utf-8')
	let buffer = ''

	while (true) {
		const { done, value } = await reader.read()
		if (done) {
			if (buffer.trim()) {
				processEventChunk(buffer)
			}
			break
		}

		buffer += decoder.decode(value, { stream: true })
		const events = buffer.split(/\r?\n\r?\n/)
		buffer = events.pop() || ''

		for (const eventChunk of events) {
			processEventChunk(eventChunk)
		}
	}
}

function getTime(): string {
	return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ChatPage() {
	const sessionIdRef = useRef(`chat-${Date.now()}`)
	const [messages, setMessages] = useState<Message[]>([
		{
			id: 0, role: 'ai', timestamp: getTime(),
			text: 'Hello! I am CitizenAI, your multilingual government services assistant. Ask me anything about public health, education, housing, or legal rights in any language you are comfortable with.',
		}
	])
	const [input, setInput] = useState('')
	const [isTyping, setIsTyping] = useState(false)
	const [selectedLang, setSelectedLang] = useState('auto')
	const [showLangDropdown, setShowLangDropdown] = useState(false)
	const bottomRef = useRef<HTMLDivElement>(null)

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
	}, [messages, isTyping])

	const sendMessage = async (text: string) => {
		if (!text.trim()) return
		const targetLang = selectedLang === 'auto' ? 'auto' : selectedLang
		const userMsg: Message = { id: Date.now(), role: 'user', text: text.trim(), timestamp: getTime() }
		const aiMessageId = Date.now() + 1
		setMessages(prev => [...prev, userMsg])
		setInput('')
		setIsTyping(true)

		try {
			let hasToken = false
			setMessages(prev => [...prev, { id: aiMessageId, role: 'ai', text: '', timestamp: getTime() }])

			await streamAIResponse(
				text.trim(),
				targetLang,
				sessionIdRef.current,
				(token) => {
					hasToken = true
					setIsTyping(false)
					setMessages(prev => prev.map(msg => (
						msg.id === aiMessageId ? { ...msg, text: msg.text + token } : msg
					)))
				}
			)

			if (!hasToken) {
				setMessages(prev => prev.map(msg => (
					msg.id === aiMessageId
						? { ...msg, text: 'No response returned from assistant.' }
						: msg
				)))
			}
		} catch (error) {
			const message = error instanceof Error
				? `Connection issue: ${error.message}`
				: 'Connection issue: Unable to reach translation service.'
			setMessages(prev => {
				const hasPlaceholder = prev.some(msg => msg.id === aiMessageId)
				if (hasPlaceholder) {
					return prev.map(msg => (
						msg.id === aiMessageId ? { ...msg, text: message } : msg
					))
				}
				return [...prev, { id: aiMessageId, role: 'ai', text: message, timestamp: getTime() }]
			})
		} finally {
			setIsTyping(false)
		}
	}

	const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) }
	}

	return (
		<div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--paper)' }}>

			<header style={{
				background: '#ffffff', borderBottom: '1px solid var(--border)',
				padding: '0 1.5rem', height: '64px',
				display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
			}}>
				<div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
					<Link href="/" style={{ color: 'var(--muted)', textDecoration: 'none', fontSize: '0.85rem' }}>
						← Back to Dashboard
					</Link>
					<span style={{ color: 'var(--border)' }}>|</span>
					<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
						<div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>🤖</div>
						<div>
							<div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--ink)' }}>CitizenAI Assistant</div>
							<div style={{ fontSize: '0.7rem', color: 'var(--teal)' }}>Online · RAG-powered</div>
						</div>
					</div>
				</div>

				<div style={{ position: 'relative' }}>
					<button onClick={() => setShowLangDropdown(v => !v)} style={{
						background: 'var(--teal-light)', border: '1px solid var(--teal)',
						borderRadius: '9999px', padding: '6px 14px',
						fontSize: '0.8rem', color: 'var(--teal)', fontWeight: 500, cursor: 'pointer',
					}}>
						{LANG_OPTIONS.find(l => l.code === selectedLang)?.label || 'Follow input language'} ▾
					</button>
					{showLangDropdown && (
						<div style={{
							position: 'absolute', top: '110%', right: 0,
							background: '#ffffff', border: '1px solid var(--border)',
							borderRadius: '10px', boxShadow: '0 4px 20px rgba(15,25,35,0.12)',
							zIndex: 200, minWidth: '160px', overflow: 'hidden',
						}}>
							{LANG_OPTIONS.map(l => (
								<button key={l.code} onClick={() => { setSelectedLang(l.code); setShowLangDropdown(false) }} style={{
									width: '100%', padding: '10px 14px', textAlign: 'left',
									background: selectedLang === l.code ? 'var(--teal-light)' : 'transparent',
									color: selectedLang === l.code ? 'var(--teal)' : 'var(--ink)',
									border: 'none', cursor: 'pointer', fontSize: '0.85rem',
									fontWeight: selectedLang === l.code ? 600 : 400,
								}}>
									{l.label}
								</button>
							))}
						</div>
					)}
				</div>
			</header>

			<div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
				<div style={{ maxWidth: '760px', margin: '0 auto', padding: '0 1.5rem' }}>

					{messages.length === 1 && (
						<div style={{ marginBottom: '28px' }}>
							<div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '10px', fontWeight: 500 }}>QUICK QUESTIONS</div>
							<div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
								{QUICK_PROMPTS.map(q => (
									<button key={q.label} onClick={() => sendMessage(q.text)} style={{
										background: '#ffffff', border: '1px solid var(--border)',
										borderRadius: '9999px', padding: '8px 16px',
										fontSize: '0.82rem', cursor: 'pointer', color: 'var(--ink)',
									}}>
										{q.label}
									</button>
								))}
							</div>
						</div>
					)}

					{messages.map(msg => (
						<div key={msg.id} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: '20px' }}>
							{msg.role === 'ai' && (
								<div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, marginRight: '10px', flexShrink: 0, alignSelf: 'flex-end' }}>🤖</div>
							)}
							<div style={{ maxWidth: '72%' }}>
								<div style={{
									padding: '12px 16px',
									borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
									background: msg.role === 'user' ? 'var(--teal)' : '#ffffff',
									color: msg.role === 'user' ? '#ffffff' : 'var(--ink)',
									border: msg.role === 'ai' ? '1px solid var(--border)' : 'none',
									fontSize: '0.9rem', lineHeight: 1.65,
								}}>
									<div className={`markdown-content ${msg.role === 'user' ? 'user-md' : 'ai-md'}`}>
										<ReactMarkdown remarkPlugins={[remarkGfm]}>
											{msg.text}
										</ReactMarkdown>
									</div>
								</div>
								<div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginTop: '4px', textAlign: msg.role === 'user' ? 'right' : 'left' }}>
									{msg.timestamp}
								</div>
							</div>
							{msg.role === 'user' && (
								<div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--gold)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, marginLeft: '10px', flexShrink: 0, alignSelf: 'flex-end' }}>👤</div>
							)}
						</div>
					))}

					{isTyping && (
						<div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', marginBottom: '20px' }}>
							<div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>🤖</div>
							<div style={{ background: '#ffffff', border: '1px solid var(--border)', borderRadius: '18px 18px 18px 4px', padding: '14px 18px', display: 'flex', gap: '5px', alignItems: 'center' }}>
								{[0, 1, 2].map(i => (
									<div key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--teal)', animation: 'bounce 1.1s ease infinite', animationDelay: `${i * 0.18}s` }} />
								))}
							</div>
						</div>
					)}

					<div ref={bottomRef} />
				</div>
			</div>

			<div style={{ background: 'var(--teal-light)', borderTop: '1px solid var(--border)', padding: '8px 1.5rem', fontSize: '0.75rem', color: 'var(--teal)', display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
				<span>📄</span>
				<span>Responses grounded in official government documents via RAG</span>
			</div>

			<div style={{ background: '#ffffff', borderTop: '1px solid var(--border)', padding: '16px 1.5rem', flexShrink: 0 }}>
				<div style={{ maxWidth: '760px', margin: '0 auto' }}>
					<div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', background: 'var(--cream)', borderRadius: '20px', padding: '10px 14px', border: '1.5px solid var(--border)' }}>
						<button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: '4px', color: 'var(--muted)', flexShrink: 0 }}>🎤</button>
						<textarea
							value={input}
							onChange={e => setInput(e.target.value)}
							onKeyDown={handleKey}
							placeholder={`Type in any language (${LANG_OPTIONS.find(l => l.code === selectedLang)?.label || 'Follow input language'})`}
							rows={1}
							style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontFamily: 'var(--font-body)', fontSize: '0.9rem', color: 'var(--ink)', resize: 'none', lineHeight: 1.5, maxHeight: '120px' }}
						/>
						<button
							onClick={() => sendMessage(input)}
							disabled={!input.trim() || isTyping}
							style={{
								background: input.trim() && !isTyping ? 'var(--teal)' : 'var(--border)',
								color: input.trim() && !isTyping ? '#ffffff' : 'var(--muted)',
								border: 'none', borderRadius: '9999px', width: 36, height: 36,
								cursor: input.trim() && !isTyping ? 'pointer' : 'default',
								display: 'flex', alignItems: 'center', justifyContent: 'center',
								fontSize: '1rem', flexShrink: 0,
							}}
						>↑</button>
					</div>
					<div style={{ textAlign: 'center', fontSize: '0.7rem', color: 'var(--muted)', marginTop: '8px' }}>
						Press Enter to send · Shift+Enter for new line · Powered by RAG + SEA-LION
					</div>
				</div>
			</div>

			<style>{`
				@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }
				.markdown-content p { margin: 0.35rem 0; }
				.markdown-content p:first-child { margin-top: 0; }
				.markdown-content p:last-child { margin-bottom: 0; }
				.markdown-content h1, .markdown-content h2, .markdown-content h3,
				.markdown-content h4, .markdown-content h5, .markdown-content h6 {
					margin: 0.35rem 0;
					font-family: var(--font-display);
					line-height: 1.3;
				}
				.markdown-content ul, .markdown-content ol {
					margin: 0.35rem 0 0.35rem 1.25rem;
				}
				.markdown-content li { margin: 0.18rem 0; }
				.markdown-content code {
					padding: 0.08rem 0.35rem;
					border-radius: 6px;
					font-size: 0.84em;
					font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
				}
				.ai-md code { background: var(--cream); color: var(--ink); }
				.user-md code { background: rgba(255,255,255,0.22); color: #ffffff; }
				.markdown-content pre {
					overflow-x: auto;
					padding: 0.55rem 0.65rem;
					border-radius: 10px;
					margin: 0.45rem 0;
				}
				.ai-md pre { background: var(--cream); }
				.user-md pre { background: rgba(255,255,255,0.2); }
				.markdown-content pre code {
					padding: 0;
					background: transparent;
				}
				.markdown-content a { text-decoration: underline; text-underline-offset: 2px; }
				.ai-md a { color: var(--teal); }
				.user-md a { color: #ffffff; }
				.markdown-content blockquote {
					margin: 0.4rem 0;
					padding: 0.2rem 0 0.2rem 0.7rem;
					border-left: 3px solid var(--border);
					opacity: 0.92;
				}
				.markdown-content hr {
					border: none;
					border-top: 1px solid var(--border);
					margin: 0.6rem 0;
				}
				.markdown-content table {
					width: 100%;
					border-collapse: collapse;
					margin: 0.4rem 0;
					font-size: 0.86rem;
				}
				.markdown-content th, .markdown-content td {
					border: 1px solid var(--border);
					padding: 0.32rem 0.45rem;
					text-align: left;
				}
				.ai-md th { background: var(--teal-light); }
				.user-md th { background: rgba(255,255,255,0.2); }
			`}</style>
		</div>
	)
}
