@echo off
chcp 65001 >nul
title 沉鱼AI畅聊助手 - 一键启动服务
color 0A
echo.
echo  ╔════════════════════════════════════════╗
echo  ║     🦞 沉鱼AI畅聊助手 v2.1            ║
echo  ║     一键启动 - 完整服务版              ║
echo  ╚════════════════════════════════════════╝
echo.

set APP_DIR=%~dp0
set PORT=5678

cd /d "%APP_DIR%"

REM ===== Step 1: 清理旧进程 =====
echo [1/4] Cleaning old processes...
tasklist /FI "IMAGENAME eq python.exe" /FO CSV 2>nul | findstr /I python >nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2 delims=," %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /I python') do taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo       Done.

REM ===== Step 2: 启动Flask后端 =====
echo [2/4] Starting Flask Backend (port %PORT%)...
start "" /B python app.py
timeout /t 4 /nobreak >nul
echo       Checking...
curl -s http://localhost:%PORT%/api/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo       ✅ Backend OK: http://localhost:%PORT%
) else (
    echo       ⚠️ Backend may still be starting... wait a moment
)

REM ===== Step 3: 启动Cloudflare Tunnel =====
echo [3/4] Starting Cloudflare Tunnel...
start "" /B cloudflared.exe tunnel --url http://localhost:%PORT%
timeout /t 8 /nobreak >nul
echo       ✅ Tunnel starting...

REM ===== Step 4: 显示状态 =====
echo.
echo [4/4] ══════════════════════════════════
echo.
echo   🟢 Local:  http://localhost:%PORT%
echo.
echo   🌐 Public URL: (see cloudflared output above)
echo      Or check: https://trycloudflare.com
echo.
echo   💡 Keep this window open for remote access!
echo   💡 Close to stop all services.
echo.
echo   Press Ctrl+C to stop all services...
echo.

REM 保持窗口打开
pause >nul

REM 停止所有相关进程
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
echo All services stopped. Bye!
