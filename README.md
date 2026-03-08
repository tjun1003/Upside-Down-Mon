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
