@echo off
echo.
echo Starting Hackathon project...
echo.

echo Cleaning old listeners on ports 8000 and 3000...
for %%P in (8000 3000) do (
	for /f "tokens=5" %%I in ('netstat -aon ^| findstr /r /c:":%%P .*LISTENING"') do (
		taskkill /PID %%I /F >nul 2>&1
	)
)

REM 启动 Python 后端
echo Starting Python backend on port 8000...
start "Python Backend" cmd /k "cd /d %~dp0src\app\api\translate && conda run -n Hackathon --no-capture-output python translation.py"

REM 等待 2 秒让后端先启动
timeout /t 2 /nobreak > nul

REM 启动 Next.js 前端
echo Starting Next.js frontend on port 3000...
start "Next.js Frontend" cmd /k "cd /d %~dp0 && npm run dev"

echo.
echo Services started.
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
echo Tip: run npm run stop:all to stop both ports quickly.
echo.
pause
