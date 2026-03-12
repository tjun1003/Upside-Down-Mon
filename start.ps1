# ═══════════════════════════════════════════════════════════════════
# 🚀 启动脚本 - 同时启动 Next.js 前端和 Python 后端
# ═══════════════════════════════════════════════════════════════════

Write-Host "🚀 启动 Hackathon 项目..." -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 启动 Python 后端 (新窗口)
Write-Host "📦 启动 Python 翻译后端 (端口 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir\src\app\api\translate'; Write-Host '🐍 使用 Conda 环境 (Hackathon)...' -ForegroundColor Magenta; conda run -n Hackathon --no-capture-output python translation.py"

# 等待一下让后端先启动
Start-Sleep -Seconds 2

# 启动 Next.js 前端 (新窗口)
Write-Host "⚛️  启动 Next.js 前端 (端口 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir'; Write-Host '⚛️ Next.js Frontend Starting...' -ForegroundColor Green; npm run dev"

Write-Host ""
Write-Host "✅ 所有服务已启动!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 前端地址: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📍 后端地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 提示: 关闭打开的 PowerShell 窗口即可停止服务" -ForegroundColor Gray
