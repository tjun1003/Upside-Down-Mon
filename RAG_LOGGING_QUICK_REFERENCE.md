# RAG 日志功能快速参考

## 📋 修改概览

已为MongoDB Atlas RAG系统添加了详细的终端日志记录。现在你可以实时看到每次RAG检索的详细信息。

## 📁 修改的文件

### 1. `src/app/api/translate/chatbot_core.py`

#### 修改点1: `_atlas_format_context()` 方法
- 添加了文档计数日志
- 为每个检索到的文档显示:
  - 文档索引号 [1], [2], etc.
  - 相关分数 (score)
  - 文档来源 (source)
  - 内容预览 (前100字)

**输出示例:**
```
📚 RAG: Found 2 document(s) from Atlas KB
  [1] Ministry of Education (score: 0.8234)
       Content: 最新的教育政策包括...
  [2] Education Notice (score: 0.7562)
       Content: 教育局发布最新通知...
```

#### 修改点2: `_atlas_retrieve()` 方法
- 记录查询文本和limit参数
- 区分向量搜索和关键字搜索，分别记录日志
- 搜索开始、成功、失败时都有对应的日志输出

**输出示例:**
```
🔍 RAG: Query: '我想知道教育局的最新资讯' (limit=3)
🔍 RAG: Attempting vector search using index 'default'...
✅ RAG: Vector search successful! Retrieved 2 document(s)
```

#### 修改点3: `retrieve()` 方法
- 完全重写，添加了结构化的日志输出
- 显示检索流程的每个阶段
- 区分Atlas KB和本地KB
- 清晰的分隔线便于在终端中识别

**输出示例:**
```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: '我想知道教育局的最新资讯'
🔍 RAG: Attempting vector search...
✅ RAG: Vector search successful! Retrieved 2 document(s)
...
✅ RAG Context prepared successfully
============================================================
```

### 2. `src/app/api/translate/translation.py`

#### 修改点: `chat_stream()` 函数中的 `event_generator()`
- 在检索RAG上下文后添加日志
- 显示是否成功使用了RAG上下文
- 记录上下文的字符数

**输出示例:**
```
📌 USING RAG CONTEXT FOR RESPONSE
Context length: 1245 characters
```

或者：
```
⚠️  NO RAG CONTEXT - Using default knowledge
```

## 🔍 日志符号速查

| 符号 | 含义 | 何时出现 |
|------|------|---------|
| 🔍 | 搜索/检索 | 检索开始 |
| ✅ | 成功 | 搜索有结果 |
| ❌ | 失败/无结果 | 搜索无结果 |
| ⚠️ | 警告/降级 | 向量搜索失败转向关键字 |
| 📚 | 文档 | 显示找到的文档信息 |
| 📌 | 标记 | 使用RAG上下文 |
| 📍 | 位置 | 源信息 |

## 🚀 如何查看日志

### 方式1: 启动后端并观察
```bash
npm run start:all
```

然后发送任何请求，在后端终端中查看日志。

### 方式2: 运行测试脚本
```powershell
# PowerShell
.\test_rag_logging.ps1

# 或 Python
python test_rag_logging.py
```

### 方式3: 使用终端发送测试请求

```powershell
$body = @{
    session_id = 'test-123'
    message = '我想知道教育局的最新资讯'
    target_lang = 'auto'
    assistant_mode = $true
} | ConvertTo-Json

Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/stream' `
    -Method Post `
    -ContentType 'application/json' `
    -Body $body
```

在后端终端中你会看到详细日志。

## ✨ 主要优势

1. ✅ **可见性**: 清楚看到RAG在做什么
2. ✅ **调试**: 快速定位检索问题
3. ✅ **性能**: 了解搜索耗时和结果质量
4. ✅ **信心**: 确认系统确实在使用知识库

## 📖 更多信息

详见 [RAG_LOGGING_GUIDE.md](./RAG_LOGGING_GUIDE.md)

## 📝 环境配置检查清单

- [ ] `USE_ATLAS_KB=1` 在 `.env` 中
- [ ] `MONGODB_ATLAS_URI` 已配置
- [ ] `MONGODB_ATLAS_DB` 已设置为 `database1`
- [ ] `MONGODB_ATLAS_COLLECTION` 已设置为 `knowledge_base`
- [ ] `MONGODB_USE_VECTOR_SEARCH=1` 已启用
- [ ] 向量索引已创建 (运行 `atlas_vector_backfill.py`)
- [ ] 知识库中有文档

## 🔧 常见问题

**Q: 为什么没有看到日志?**
- A: 确保MongoDB已连接且 `USE_ATLAS_KB=1`

**Q: 日志中带有绿色对勾但没有文档?**
- A: 知识库连接成功但没有匹配的文档。检查数据和向量索引。

**Q: 看到警告符号?**
- A: 可能向量搜索失败而自动降级到关键字搜索，或数据不匹配。

查看 [RAG_LOGGING_GUIDE.md](./RAG_LOGGING_GUIDE.md) 获得完整故障排除指南。
