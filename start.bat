@echo off
REM ═══════════════════════════════════════════════════════════════════
REM 🚀 启动脚本 - 双击即可运行
REM ═══════════════════════════════════════════════════════════════════

echo.
echo 🚀 启动 Hackathon 项目...
echo.

REM 启动 Python 后端
echo 📦 启动 Python 翻译后端 (端口 8000)...
start "Python Backend" cmd /k "cd /d %~dp0src\app\api\translate && conda run -n Hackathon --no-capture-output python translation.py"

REM 等待 2 秒让后端先启动
timeout /t 2 /nobreak > nul

REM 启动 Next.js 前端
echo ⚛️  启动 Next.js 前端 (端口 3000)...
start "Next.js Frontend" cmd /k "cd /d %~dp0 && npm run dev"

echo.
echo ✅ 所有服务已启动!
echo.
echo 📍 前端地址: http://localhost:3000
echo 📍 后端地址: http://localhost:8000
echo.
echo 💡 提示: 关闭打开的命令行窗口即可停止服务
echo.
pause
