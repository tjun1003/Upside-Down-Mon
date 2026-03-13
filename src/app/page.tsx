'use client'
import React, { useState, useEffect } from 'react'
import Link from 'next/link'

const LANGUAGES = ['English', 'Bahasa Melayu', 'ภาษาไทย', 'Tagalog', 'Tiếng Việt', '普通话', 'Bahasa Indonesia']

const SERVICES = [
  { icon: '🏥', label: 'Public Health', desc: 'Healthcare subsidies, clinic locator, vaccination records', color: '#e0f4f0', url: 'https://www.moh.gov.my' },
  { icon: '⚖️', label: 'Legal Aid', desc: 'Know your rights, legal assistance programmes', color: '#fdf3e0', url: 'https://www.legalaid.gov.my' },
  { icon: '🎓', label: 'Education', desc: 'Scholarships, school enrolment, training grants', color: '#f0e8f8', url: 'https://www.moe.gov.my' },
  { icon: '🏠', label: 'Housing', desc: 'Affordable housing applications, rental assistance', color: '#e8f0fb', url: 'https://ehome.kpkt.gov.my' },
  { icon: '💼', label: 'Employment', desc: 'Job matching, skills reskilling, unemployment aid', color: '#fce8e8', url: 'https://www.jobsmalaysia.gov.my' },
  { icon: '🌾', label: 'Rural Support', desc: 'Agricultural subsidies, rural development funds', color: '#eef5e0', url: 'https://www.kplb.gov.my' },
]

const STATS = [
  { value: '12', label: 'Languages supported' },
  { value: '40+', label: 'Dialects & variants' },
  { value: '6', label: 'Government service areas' },
  { value: '24/7', label: 'AI assistance' },
]

export default function DashboardPage() {
  const [langIdx, setLangIdx] = useState(0)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    setVisible(true)
    const id = setInterval(() => setLangIdx(i => (i + 1) % LANGUAGES.length), 1800)
    return () => clearInterval(id)
  }, [])

  return React.createElement('div', { style: { minHeight: '100vh', background: 'var(--paper)' } },

    React.createElement('nav', {
      style: {
        position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(245,240,232,0.92)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)',
        padding: '0 2rem', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', height: '64px',
      }
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' } },
        React.createElement('span', { style: { width: 36, height: 36, borderRadius: '50%', background: 'var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 } }, '🌐'),
        React.createElement('span', { style: { fontFamily: 'var(--font-display)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--ink)' } }, 'CitizenAI')
      ),
      React.createElement('div', { style: { display: 'flex', gap: '2rem', fontSize: '0.875rem' } },
        ['Services', 'About', 'Languages', 'Help'].map(item =>
          React.createElement('a', { key: item, href: '#', style: { color: 'var(--muted)', textDecoration: 'none' } }, item)
        )
      ),
      React.createElement(Link, {
        href: '/chat',
        style: { background: 'var(--teal)', color: '#ffffff', padding: '8px 20px', borderRadius: '9999px', textDecoration: 'none', fontSize: '0.875rem', fontWeight: 500, display: 'inline-block' }
      }, 'Open Assistant')
    ),

    React.createElement('section', {
      style: {
        maxWidth: '1160px', margin: '0 auto', padding: '80px 2rem 60px',
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4rem', alignItems: 'center',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 0.7s ease, transform 0.7s ease',
      }
    },
      React.createElement('div', null,
        React.createElement('div', {
          style: { display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'var(--teal-light)', border: '1px solid var(--teal)', borderRadius: '9999px', padding: '6px 14px', fontSize: '0.8rem', color: 'var(--teal)', fontWeight: 500, marginBottom: '1.5rem' }
        },
          React.createElement('span', { style: { width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', display: 'inline-block' } }),
          'Now speaking: ',
          React.createElement('strong', null, LANGUAGES[langIdx])
        ),
        React.createElement('h1', {
          style: { fontFamily: 'var(--font-display)', fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)', fontWeight: 700, lineHeight: 1.15, color: 'var(--ink)', marginBottom: '1.25rem' }
        },
          'Government services,',
          React.createElement('br', null),
          React.createElement('em', { style: { color: 'var(--teal)', fontStyle: 'italic' } }, 'in your language.')
        ),
        React.createElement('p', {
          style: { fontSize: '1.05rem', color: 'var(--muted)', lineHeight: 1.7, maxWidth: '420px', marginBottom: '2rem' }
        }, 'CitizenAI translates and simplifies complex official information across 12+ ASEAN languages so every citizen can access the support they deserve.'),
        React.createElement('div', { style: { display: 'flex', gap: '12px', flexWrap: 'wrap' } },
          React.createElement(Link, { href: '/chat', style: { background: 'var(--teal)', color: '#ffffff', padding: '14px 28px', borderRadius: '9999px', textDecoration: 'none', fontWeight: 600, fontSize: '0.95rem', display: 'inline-block' } }, 'Ask CitizenAI'),
          React.createElement('a', { href: '#services', style: { background: 'transparent', color: 'var(--ink)', padding: '14px 28px', borderRadius: '9999px', textDecoration: 'none', fontWeight: 500, fontSize: '0.95rem', border: '1.5px solid var(--border)', display: 'inline-block' } }, 'Browse services')
        )
      ),
      React.createElement('div', null,
        React.createElement('div', {
          style: { background: '#ffffff', borderRadius: '20px', border: '1px solid var(--border)', padding: '28px', boxShadow: '0 12px 48px rgba(15,25,35,0.16)' }
        },
          React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' } },
            React.createElement('div', { style: { width: 36, height: 36, borderRadius: '50%', background: 'var(--teal)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 } }, '🤖'),
            React.createElement('div', null,
              React.createElement('div', { style: { fontWeight: 600, fontSize: '0.875rem' } }, 'CitizenAI Assistant'),
              React.createElement('div', { style: { fontSize: '0.75rem', color: 'var(--teal)' } }, 'Online')
            )
          ),
          [
            { role: 'user', msg: 'Macam mana nak mohon subsidi hospital?', lang: 'Bahasa Melayu' },
            { role: 'ai', msg: 'Anda boleh mohon melalui portal MySejahtera.' },
            { role: 'user', msg: 'ขอความช่วยเหลือด้านการศึกษา', lang: 'Thai' },
            { role: 'ai', msg: 'ยินดีช่วยเหลือ! ฉันสามารถแนะนำทุนการศึกษาได้' },
          ].map((m, i) =>
            React.createElement('div', { key: i, style: { display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: '10px' } },
              React.createElement('div', {
                style: { maxWidth: '80%', padding: '8px 12px', borderRadius: m.role === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px', background: m.role === 'user' ? 'var(--teal)' : 'var(--cream)', color: m.role === 'user' ? '#ffffff' : 'var(--ink)', fontSize: '0.78rem', lineHeight: 1.5 }
              },
                m.lang ? React.createElement('div', { style: { fontSize: '0.65rem', opacity: 0.7, marginBottom: 2 } }, m.lang) : null,
                m.msg
              )
            )
          ),
          React.createElement('div', {
            style: { marginTop: '12px', border: '1px solid var(--border)', borderRadius: '9999px', padding: '8px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--muted)' }
          },
            React.createElement('span', null, 'Type or speak in any language'),
            React.createElement('span', null, '🎤')
          )
        )
      )
    ),

    React.createElement('section', { style: { background: 'var(--teal)', padding: '40px 2rem' } },
      React.createElement('div', { style: { maxWidth: '1160px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '2rem' } },
        STATS.map(s =>
          React.createElement('div', { key: s.label, style: { textAlign: 'center' } },
            React.createElement('div', { style: { fontFamily: 'var(--font-display)', fontSize: '2.4rem', fontWeight: 700, color: 'var(--gold-light)' } }, s.value),
            React.createElement('div', { style: { fontSize: '0.85rem', color: 'rgba(255,255,255,0.75)', marginTop: '4px' } }, s.label)
          )
        )
      )
    ),

    React.createElement('section', { id: 'services', style: { maxWidth: '1160px', margin: '0 auto', padding: '80px 2rem' } },
      React.createElement('div', { style: { marginBottom: '48px' } },
        React.createElement('div', { style: { fontFamily: 'var(--font-display)', fontSize: 'clamp(1.8rem, 3vw, 2.6rem)', fontWeight: 700, color: 'var(--ink)', marginBottom: '0.75rem' } }, 'Services we can help with'),
        React.createElement('p', { style: { color: 'var(--muted)', maxWidth: '480px' } }, 'Ask our AI in any language. We will retrieve, simplify, and explain official government information instantly.')
      ),
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' } },
        SERVICES.map(s =>
          React.createElement('div', { key: s.label, style: { background: '#ffffff', borderRadius: '20px', border: '1px solid var(--border)', padding: '28px' } },
            React.createElement('div', { style: { width: 48, height: 48, borderRadius: '10px', background: s.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', marginBottom: '14px' } }, s.icon),
            React.createElement('div', { style: { fontWeight: 600, fontSize: '1rem', marginBottom: '6px', color: 'var(--ink)' } }, s.label),
            React.createElement('div', { style: { fontSize: '0.85rem', color: 'var(--muted)', lineHeight: 1.6, marginBottom: '14px' } }, s.desc),
            React.createElement('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' } },
              React.createElement('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer', style: { fontSize: '0.78rem', color: '#ffffff', background: 'var(--teal)', padding: '5px 12px', borderRadius: '9999px', textDecoration: 'none', fontWeight: 500 } }, 'Visit Gov Site'),
              React.createElement(Link, { href: '/chat', style: { fontSize: '0.78rem', color: 'var(--teal)', background: 'var(--teal-light)', padding: '5px 12px', borderRadius: '9999px', textDecoration: 'none', fontWeight: 500 } }, 'Ask AI')
            )
          )
        )
      )
    ),

    React.createElement('section', {
      style: { background: 'var(--ink)', margin: '0 auto 80px', borderRadius: '20px', padding: '60px 48px', maxWidth: '1160px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '2rem' }
    },
      React.createElement('div', null,
        React.createElement('h2', { style: { fontFamily: 'var(--font-display)', fontSize: '2rem', color: 'var(--paper)', fontWeight: 700, marginBottom: '8px' } }, 'Ready to get help?'),
        React.createElement('p', { style: { color: 'rgba(245,240,232,0.6)', fontSize: '0.95rem' } }, 'No forms. No jargon. Just ask in the language you are most comfortable with.')
      ),
      React.createElement(Link, { href: '/chat', style: { background: 'var(--gold)', color: 'var(--ink)', padding: '16px 32px', borderRadius: '9999px', textDecoration: 'none', fontWeight: 700, fontSize: '0.95rem', display: 'inline-block', whiteSpace: 'nowrap' } }, 'Open CitizenAI Chat')
    ),

    React.createElement('footer', {
      style: { borderTop: '1px solid var(--border)', padding: '32px 2rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--muted)' }
    },
      React.createElement('div', { style: { marginBottom: '8px', fontFamily: 'var(--font-display)', fontSize: '1rem', color: 'var(--ink)' } }, 'CitizenAI'),
      'Built for V Hack 2026 · Case Study 4 · Multilingual AI for Public Services'
    ),

    React.createElement('style', null, `
      @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    `)
  )
}
