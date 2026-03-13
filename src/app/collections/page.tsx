'use client'
import React, { useState, useRef, useEffect } from 'react'
import Link from 'next/link'

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
  { code: 'en', label: 'English' },
  { code: 'ms', label: 'Bahasa Melayu' },
  { code: 'th', label: 'ภาษาไทย' },
  { code: 'tl', label: 'Tagalog' },
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'zh', label: '中文' },
  { code: 'id', label: 'Bahasa Indonesia' },
]

const AI_RESPONSES: Record<string, string> = {
  default: 'I understand your question. Based on official government documents, this service is available to all residents. You may apply online via the government portal or visit your nearest service centre. Would you like me to explain further?',
  subsidy: 'Hospital subsidies are available under the Skim Peduli Kesihatan programme. To apply: (1) Register at MySejahtera portal, (2) Upload your IC and income documents, (3) Visit any government clinic for assessment. The process takes 5 to 7 working days.',
  scholarship: 'Several scholarships are available: JPA Scholarship (full tuition), MARA Loans (low-interest), and State Education Bursaries. Eligibility depends on household income and academic results. Which education level is your child in?',
  housing: 'Affordable housing programmes include PR1MA for middle income, PPR Rental for low income, and MyDeposit for first-home buyers. Apply online at ehome.kpkt.gov.my. What is your household income range?',
  legal: 'As a migrant worker you have the right to fair wages, safe working conditions, healthcare access, and the right to file complaints with JTKSM. Call the Labour Hotline: 1800-88-8088 (free). Would you like this in another language?',
}

function getAIResponse(text: string): string {
  const lower = text.toLowerCase()
  if (lower.includes('subsidi') || lower.includes('hospital') || lower.includes('health')) return AI_RESPONSES.subsidy
  if (lower.includes('scholarship') || lower.includes('education') || lower.includes('school')) return AI_RESPONSES.scholarship
  if (lower.includes('hous') || lower.includes('rumah')) return AI_RESPONSES.housing
  if (lower.includes('legal') || lower.includes('right') || lower.includes('migrant')) return AI_RESPONSES.legal
  return AI_RESPONSES.default
}

function getTime(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0, role: 'ai', timestamp: getTime(),
      text: 'Hello! I am CitizenAI, your multilingual government services assistant. Ask me anything about public health, education, housing, or legal rights in any language you are comfortable with.',
    }
  ])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [selectedLang, setSelectedLang] = useState('en')
  const [showLangDropdown, setShowLangDropdown] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const sendMessage = async (text: string) => {
    if (!text.trim()) return
    const userMsg: Message = { id: Date.now(), role: 'user', text: text.trim(), timestamp: getTime() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)
    await new Promise(r => setTimeout(r, 1200 + Math.random() * 600))
    const aiMsg: Message = { id: Date.now() + 1, role: 'ai', text: getAIResponse(text), timestamp: getTime() }
    setIsTyping(false)
    setMessages(prev => [...prev, aiMsg])
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
            {LANG_OPTIONS.find(l => l.code === selectedLang)?.label} ▾
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
                  {msg.text}
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
              placeholder={`Type in any language (${LANG_OPTIONS.find(l => l.code === selectedLang)?.label})`}
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
      `}</style>
    </div>
  )
}
