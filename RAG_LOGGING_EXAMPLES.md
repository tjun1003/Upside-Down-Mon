# RAG 日志输出示例

这个文件展示了启用RAG日志后你会看到的实际终端输出示例。

## 场景 1: 向量搜索成功

```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: '我想知道教育局的最新资讯'
🔍 RAG: Query: '我想知道教育局的最新资讯' (limit=3)
🔍 RAG: Attempting vector search using index 'default'...
✅ RAG: Vector search successful! Retrieved 2 document(s)
📚 RAG: Found 2 document(s) from Atlas KB
  [1] Ministry of Education Portal (score: 0.8923)
       Content: 教育部最新发布的政策文件包括: 1. 2024年高考改革方案... 2.
  [2] Education News & Updates (score: 0.8234)
       Content: 教育局最新通知: 本年度教育工作重点包括提升教学质量、推进数
✅ RAG Context prepared successfully
============================================================

📌 USING RAG CONTEXT FOR RESPONSE
Context length: 1245 characters
```

## 场景 2: 向量搜索失败，自动降级到关键字搜索

```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: '一些模糊的查询'
🔍 RAG: Query: '一些模糊的查询' (limit=3)
🔍 RAG: Attempting vector search using index 'default'...
❌ RAG: Vector search returned no results
🔍 RAG: Attempting keyword search...
✅ RAG: Keyword search successful! Retrieved 1 document(s)
📚 RAG: Found 1 document(s) from Atlas KB
  [1] General Government Services (score: 0.0)
       Content: 政府部门提供多项公共服务，包括教育、医疗、住房等。有关详
✅ RAG Context prepared successfully
============================================================

📌 USING RAG CONTEXT FOR RESPONSE
Context length: 256 characters
```

## 场景 3: 向量搜索失败，关键字搜索也失败

```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: 'random gibberish xyz123'
🔍 RAG: Query: 'random gibberish xyz123' (limit=3)
🔍 RAG: Attempting vector search using index 'default'...
❌ RAG: Vector search returned no results
🔍 RAG: Attempting keyword search...
❌ RAG: Keyword search returned no results
❌ RAG: No documents found for query
⚠️  Falling back to local knowledge base...
❌ Local KB not available
============================================================

⚠️  NO RAG CONTEXT - Using default knowledge
```

## 场景 4: 使用本地知识库（当MongoDB不可用时）

```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: '医疗补助申请步骤'
🔍 RAG: MongoDB不可用，尝试本地KB...
⚠️  Falling back to local knowledge base...
✅ Local KB: Found 3 document(s)
  [1] Healthcare Subsidy Program - Requirements
  [2] Application Process and Timeline
  [3] Document Checklist
✅ RAG Context prepared successfully
============================================================

📌 USING RAG CONTEXT FOR RESPONSE
Context length: 892 characters
```

## 完整的交互示例

### PowerShell 请求

```powershell
$body = @{
    session_id = 'demo-20260320-001'
    message = '我想了解家庭补贴'
    target_lang = 'auto'
    assistant_mode = $true
} | ConvertTo-Json

Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/stream' `
    -Method Post `
    -ContentType 'application/json' `
    -Body $body `
    -TimeoutSec 60
```

### 后端终端输出

```
2026-03-20 14:35:22 [INFO] ============================================================
2026-03-20 14:35:22 [INFO] RAG RETRIEVAL STARTED
2026-03-20 14:35:22 [INFO] ============================================================
2026-03-20 14:35:22 [INFO] Query: '我想了解家庭补贴'
2026-03-20 14:35:22 [INFO] 🔍 RAG: Query: '我想了解家庭补贴' (limit=3)
2026-03-20 14:35:22 [INFO] 🔍 RAG: Attempting vector search using index 'default'...
2026-03-20 14:35:23 [INFO] ✅ RAG: Vector search successful! Retrieved 2 document(s)
2026-03-20 14:35:23 [INFO] 📚 RAG: Found 2 document(s) from Atlas KB
2026-03-20 14:35:23 [INFO]   [1] Housing Assistance Program (score: 0.8756)
2026-03-20 14:35:23 [INFO]        Content: PR1MA计划为中等收入家庭提供经济型住房...
2026-03-20 14:35:23 [INFO]   [2] Affordable Housing Schemes (score: 0.7923)
2026-03-20 14:35:23 [INFO]        Content: 政府提供多项经济型住房计划，旨在帮助...

2026-03-20 14:35:23 [INFO] ✅ RAG Context prepared successfully
2026-03-20 14:35:23 [INFO] ============================================================

2026-03-20 14:35:23 [INFO] 📌 USING RAG CONTEXT FOR RESPONSE
2026-03-20 14:35:23 [INFO] Context length: 1567 characters

[生成回应中...]

2026-03-20 14:35:24 [INFO] Message received: '我想了解家庭补贴'
2026-03-20 14:35:24 [INFO] Source language: zh
2026-03-20 14:35:24 [INFO] Target language: zh
2026-03-20 14:35:24 [INFO] Response generated with RAG context
```

### 客户端收到的响应

```json
data: {"type":"meta","src_lang":"zh","src_name":"Chinese","confidence":0.95,"tgt_lang":"zh"}

data: {"type":"token","text":"根 "}
data: {"type":"token","text":"据 "}
data: {"type":"token","text":"最 "}
data: {"type":"token","text":"新 "}
data: {"type":"token","text":"政 "}
...
data: {"type":"done"}
```

## 日志的诊断价值

### 1. 验证后端是否在运行

如果没有看到任何日志，后端可能没有运行：
```bash
npm run start:all
```

### 2. 检查MongoDB连接

如果看到 "❌ MongoDB not available"，检查：
- MongoDB Atlas URI 是否正确
- 网络连接
- IP白名单

### 3. 评估知识库质量

- 高分数（>0.8）表示相关性很好
- 低分数（<0.5）可能需要调整查询或知识库内容
- 空结果表示查询与知识库不匹配

### 4. 定位性能瓶颈

看日志的时间戳可以判断：
- 向量搜索耗时多长
- 降级到关键字搜索是否频繁

## 调整日志详细度

如果日志过多或过少，可以修改 `translation_config.py`：

```python
# 增加日志详细度
logging.basicConfig(level=logging.DEBUG, ...)

# 减少日志（仅显示重要信息）
logging.basicConfig(level=logging.WARNING, ...)
```

## 接下来做什么

1. ✅ 启动后端: `npm run start:all`
2. ✅ 发送测试请求，观察日志
3. ✅ 根据日志调整RAG配置（见 RAG_LOGGING_GUIDE.md）
4. ✅ 如需改进，运行向量回填: `python src/app/api/translate/atlas_vector_backfill.py --force`
