# MongoDB Atlas RAG 日志指南

## 概述

现在系统已配置为在检索知识库时输出详细的日志信息，你可以在终端中实时看到：
- 正在执行的检索查询
- 使用的搜索方法（向量搜索或关键字搜索）
- 找到的文档数量
- 每个文档的相关分数
- 文档来源和内容摘要

## 启用 RAG 日志

### 1. 确保 MongoDB Atlas 已配置

检查 `.env` 文件中的以下变量：

```env
USE_KB=0                                    # 保持为0以加快启动
USE_ATLAS_KB=1                              # 必须为1来启用MongoDB Atlas KB
MONGODB_ATLAS_URI=mongodb+srv://...         # 你的MongoDB连接字符串
MONGODB_ATLAS_DB=database1                  # 数据库名称
MONGODB_ATLAS_COLLECTION=knowledge_base     # 集合名称
MONGODB_USE_VECTOR_SEARCH=1                 # 启用向量搜索
```

### 2. 启动服务

```bash
npm run start:all
```

或单独启动后端：

```bash
cd src/app/api/translate
python -m uvicorn translation:app --reload --host 127.0.0.1 --port 8000
```

### 3. 观察终端输出

当系统处理请求时，你会看到以下日志输出：

```
============================================================
RAG RETRIEVAL STARTED
============================================================
Query: '我想知道教育局的最新资讯'
🔍 RAG: Attempting vector search using index 'default'...
✅ RAG: Vector search successful! Retrieved 2 document(s)
📚 RAG: Found 2 document(s) from Atlas KB
  [1] Ministry of Education (score: 0.8234)
       Content: 最新的教育政策包括...
  [2] Education Department Notice (score: 0.7562)
       Content: 教育局发布最新通知...
✅ RAG Context prepared successfully
============================================================

📌 USING RAG CONTEXT FOR RESPONSE
Context length: 1245 characters
```

## 日志符号说明

| 符号 | 含义 |
|------|------|
| 🔍 | 正在进行搜索 |
| ✅ | 搜索成功 |
| ❌ | 没有找到结果 |
| ⚠️ | 警告或降级处理 |
| 📚 | 文档检索信息 |
| 📌 | 正在使用RAG上下文 |
| 📍 | 位置/来源信息 |

## 常见场景

### 场景 1: 向量搜索成功

```
🔍 RAG: Attempting vector search using index 'default'...
✅ RAG: Vector search successful! Retrieved 3 document(s)
📚 RAG: Found 3 document(s) from Atlas KB
  [1] Healthcare Subsidies (score: 0.8923)
  [2] Medical Aid Program (score: 0.8234)
  [3] Hospital Support (score: 0.7456)
```

### 场景 2: 向量搜索失败，自动降级到关键字搜索

```
🔍 RAG: Attempting vector search using index 'default'...
⚠️  RAG: Vector retrieval failed, fallback to keyword search: [error details]
🔍 RAG: Attempting keyword search...
✅ RAG: Keyword search successful! Retrieved 2 document(s)
```

### 场景 3: 没有找到相关文档

```
🔍 RAG: Attempting vector search using index 'default'...
❌ RAG: Vector search returned no results
🔍 RAG: Attempting keyword search...
❌ RAG: Keyword search returned no results
❌ RAG: No documents found for query
⚠️  NO RAG CONTEXT - Using default knowledge
```

## 调试技巧

### 1. 检查索引是否创建

在后端Python终端中运行：

```python
from chatbot_core import KnowledgeBase
kb = KnowledgeBase()
# 查看创建的日志信息
```

### 2. 查看数据库中的文档

使用MongoDB Compass或MongoDB Atlas Web UI查看：
- 数据库: `database1`
- 集合: `knowledge_base`
- 检查文档中是否有 `embedding` 字段（向量搜索需要）

### 3. 验证向量搜索索引

在MongoDB Atlas Web UI中：
1. 进入你的集群
2. 选择 Search Indexes
3. 确认 `default` 索引存在并且状态为 READY

### 4. 增加日志详细度

编辑 `translation_config.py`：

```python
# 修改日志级别为DEBUG
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
```

## 性能优化提示

### 1. 向量搜索慢？

检查索引配置：
```env
MONGODB_RAG_NUM_CANDIDATES=60  # 增加候选数量
MONGODB_RAG_TOP_K=3            # 最终返回结果数
```

### 2. 关键字搜索误触发？

在 `.env` 中调整相关性阈值：
```env
RAG_CONTEXT_MIN_SCORE=0.55     # 降低可以包含更多结果，提高得到匹配
```

## 测试 RAG 日志

运行测试脚本来验证日志功能：

```bash
python test_rag_logging.py
```

这将显示详细的日志输出，帮助你诊断任何问题。

## 常见问题

**Q: 为什么没有看到RAG日志？**
- A: 确保 `USE_ATLAS_KB=1` 在 `.env` 中
- 确保MongoDB连接字符串正确
- 检查知识库中是否有文档

**Q: 为什么都是关键字搜索，没有向量搜索？**
- A: 检查是否运行了向量回填脚本：
  ```bash
  python src/app/api/translate/atlas_vector_backfill.py
  ```

**Q: 相关分数很低，怎么办？**
- A: 调整 `RAG_CONTEXT_MIN_SCORE` 阈值，或者检查你的知识库内容是否相关

## 更多信息

查看以下文件了解更多：
- `src/app/api/translate/chatbot_core.py` - KnowledgeBase 类实现
- `src/app/api/translate/atlas_vector_backfill.py` - 向量索引回填脚本
- `src/app/api/translate/translation_config.py` - 配置说明
