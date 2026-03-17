# Next.js React Frontend

一个使用 Next.js 和 React 构建的现代前端应用。

## 技术栈

- **Next.js** - React 框架
- **React** - UI 库
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **ESLint** - 代码检查

## 开始使用

### 开发模式

```bash
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000) 查看应用。

### 构建生产版本

```bash
npm run build
```

### 启动生产服务器

```bash
npm start
```

### 代码检查

```bash
npm run lint
```

## 项目结构

```
├── src/
│   ├── app/           # App Router 页面和布局
│   │   ├── layout.tsx # 根布局
│   │   ├── page.tsx   # 首页
│   │   └── globals.css # 全局样式
│   └── components/    # 可复用组件
├── public/            # 静态资源
├── tailwind.config.ts # Tailwind 配置
├── tsconfig.json      # TypeScript 配置
└── next.config.ts     # Next.js 配置
```

## 了解更多

- [Next.js 文档](https://nextjs.org/docs)
- [React 文档](https://react.dev)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)

## MongoDB Atlas RAG 配置

后端位于 `src/app/api/translate/translation.py`，已支持 MongoDB Atlas 作为知识库检索源（Atlas 优先，本地索引兜底）。

1. 编辑 `src/app/api/translate/.env`（可参考 `.env.example`）并设置：

```env
USE_ATLAS_KB=1
MONGODB_ATLAS_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_ATLAS_DB=<你的数据库名>
MONGODB_ATLAS_COLLECTION=<你的集合名>

# 字段映射（按你的文档结构调整）
MONGODB_TEXT_FIELD=text
MONGODB_SOURCE_FIELD=source
MONGODB_METADATA_FIELD=metadata

# 如已配置 Atlas Vector Search（推荐）
MONGODB_USE_VECTOR_SEARCH=1
MONGODB_EMBEDDING_FIELD=embedding
MONGODB_ATLAS_VECTOR_INDEX=default
MONGODB_RAG_TOP_K=3
MONGODB_RAG_NUM_CANDIDATES=60
```

2. 安装后端依赖（至少包含 `pymongo` 与 `motor`）：

```bash
conda run -n Hackathon pip install pymongo motor
```

	如果 `motor` 在 conda 默认源找不到，请优先使用上面的 `pip install` 方式。
3. 启动项目后访问后端健康检查：`http://localhost:8000/health`。
4. 确认返回中 `atlas_kb_enabled=true` 且 `atlas_kb_ready=true`。

如果你还没在 Atlas 建立向量索引，可先把 `MONGODB_USE_VECTOR_SEARCH=0`，系统会自动回退为关键词检索。

如果你的集合还没有 embedding 字段，可以运行：

```bash
conda run -n Hackathon python src/app/api/translate/atlas_vector_backfill.py --batch-size 16
```

当前这个项目接入的 Atlas 集合实际字段示例是：

```env
MONGODB_TEXT_FIELD=Detailed Context
MONGODB_SOURCE_FIELD=Title
MONGODB_USE_VECTOR_SEARCH=1
```
