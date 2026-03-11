'use client'

import { useState } from 'react'

// 支持的语言列表
const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'zh', name: '中文' },
  { code: 'ms', name: 'Bahasa Melayu' },
  { code: 'id', name: 'Bahasa Indonesia' },
  { code: 'th', name: 'ไทย (Thai)' },
  { code: 'vi', name: 'Tiếng Việt' },
  { code: 'tl', name: 'Filipino' },
  { code: 'my', name: 'မြန်မာ (Burmese)' },
  { code: 'ta', name: 'தமிழ் (Tamil)' },
  { code: 'km', name: 'ភាសាខ្មែរ (Khmer)' },
  { code: 'lo', name: 'ລາວ (Lao)' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' },
]

interface TranslationResult {
  translation: string
  src_lang: string
  src_name: string
  confidence: number
  tgt_lang: string
  tgt_name: string
  session_id: string
  timestamp: string
}

export default function CollectionsPage() {
  const [inputText, setInputText] = useState('')
  const [targetLang, setTargetLang] = useState('en')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<TranslationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleTranslate = async () => {
    if (!inputText.trim()) {
      setError('请输入要翻译的文本')
      return
    }

    setIsLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('/api/translate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputText,
          target_lang: targetLang,
          session_id: 'user-session',
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || '翻译失败')
      }

      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '翻译服务出错，请稍后重试')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            🌏 东南亚语言翻译
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            自动检测语言并翻译到目标语言
          </p>
        </div>

        {/* 翻译界面 */}
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
          {/* 输入区域 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              输入文本（自动检测语言）
            </label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="在这里输入要翻译的文本..."
              rows={4}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg 
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                       focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       placeholder-gray-400 dark:placeholder-gray-500"
            />
          </div>

          {/* 目标语言选择 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              翻译到
            </label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="w-full sm:w-auto px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                       focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>

          {/* 翻译按钮 */}
          <button
            onClick={handleTranslate}
            disabled={isLoading || !inputText.trim()}
            className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400
                     text-white font-medium rounded-lg transition-colors
                     flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                翻译中...
              </>
            ) : (
              '翻译'
            )}
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* 翻译结果 */}
        {result && (
          <div className="mt-6 bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <span className="px-3 py-1 text-sm bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-full">
                {result.src_name} → {result.tgt_name}
              </span>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                置信度: {(result.confidence * 100).toFixed(1)}%
              </span>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <p className="text-lg text-gray-900 dark:text-white whitespace-pre-wrap">
                {result.translation}
              </p>
            </div>
          </div>
        )}

        {/* 返回首页 */}
        <div className="mt-8 text-center">
          <a
            href="/"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            ← 返回首页
          </a>
        </div>
      </div>
    </main>
  )
}
