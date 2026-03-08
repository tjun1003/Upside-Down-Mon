'use client'

import { useState } from 'react'

interface CollectionItem {
  id: string
  name: string
  type: 'code' | 'model'
  description: string
  tags: string[]
  createdAt: string
  starred: boolean
}

const initialItems: CollectionItem[] = [
  {
    id: '1',
    name: 'ResNet50 图分类',
    type: 'model',
    description: '基于 ResNet50 的图像分类预训练模型',
    tags: ['PyTorch', 'CNN', '图像分类'],
    createdAt: '2026-03-01',
    starred: true,
  },
  {
    id: '2',
    name: 'BERT 文本分类训练代码',
    type: 'code',
    description: '使用 Hugging Face Transformers 的 BERT 微调代码',
    tags: ['NLP', 'Transformers', 'Python'],
    createdAt: '2026-03-05',
    starred: false,
  },
  {
    id: '3',
    name: 'YOLO 目标检测模型',
    type: 'model',
    description: 'YOLOv8 目标检测预训练权重',
    tags: ['目标检测', 'YOLO', 'Computer Vision'],
    createdAt: '2026-03-08',
    starred: true,
  },
]

export default function CollectionsPage() {
  const [items, setItems] = useState<CollectionItem[]>(initialItems)
  const [filter, setFilter] = useState<'all' | 'code' | 'model'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const toggleStar = (id: string) => {
    setItems(items.map(item => 
      item.id === id ? { ...item, starred: !item.starred } : item
    ))
  }

  const filteredItems = items.filter(item => {
    const matchesFilter = filter === 'all' || item.type === filter
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    return matchesFilter && matchesSearch
  })

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-6xl mx-auto">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            📚 我的收
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            收藏的模型训练代码和模型
          </p>
        </div>

        {/* 搜索和筛选 */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <input
            type="text"
            placeholder="搜索收藏..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
              }`}
            >
              全部
            </button>
            <button
              onClick={() => setFilter('code')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                filter === 'code'
                  ? 'bg-green-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
              }`}
            >
              💻 代码
            </button>
            <button
              onClick={() => setFilter('model')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                filter === 'model'
                  ? 'bg-purple-600 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'
              }`}
            >
              🧠 模型
            </button>
          </div>
        </div>

        {/* 收藏列表 */}
        <div className="grid gap-4">
          {filteredItems.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              没有找到匹配的收藏项
            </div>
          ) : (
            filteredItems.map((item) => (
              <div
                key={item.id}
                className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm 
                         border border-gray-200 dark:border-gray-700
                         hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        item.type === 'code'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                          : 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                      }`}>
                        {item.type === 'code' ? '💻 代码' : '🧠 模型'}
                      </span>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {item.name}
                      </h3>
                    </div>
                    <p className="text-gray-600 dark:text-gray-400 mb-3">
                      {item.description}
                    </p>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 
                                   text-gray-600 dark:text-gray-300 rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <span className="text-sm text-gray-400">
                      收藏于 {item.createdAt}
                    </span>
                  </div>
                  <button
                    onClick={() => toggleStar(item.id)}
                    className="text-2xl hover:scale-110 transition-transform"
                    title={item.starred ? '取消星标' : '添加星标'}
                  >
                    {item.starred ? '⭐' : '☆'}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* 添加按钮 */}
        <button
          className="fixed bottom-8 right-8 w-14 h-14 bg-blue-600 hover:bg-blue-700 
                   text-white rounded-full shadow-lg flex items-center justify-center
                   text-2xl transition-colors"
          title="添加新收藏"
        >
          +
        </button>

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
