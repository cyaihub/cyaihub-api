@echo off
chcp 65001 >nul
REM ============================================================
REM  沉鱼AI畅聊助手 - Windows开机自启脚本
REM  功能：后台启动Flask后端 + 自动配置Cloudflare Tunnel
REM  用法：放入启动文件夹实现开机自启
REM ============================================================

set APP_DIR=%~dp0
set PYTHON=python
set PORT=5678

echo [沉鱼AI] Starting backend service...
echo [沉鱼AI] App directory: %APP_DIR%

cd /d "%APP_DIR%"

REM 检查端口是否已被占用
netstat -ano | findstr ":%PORT%.*LISTEN" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [沉鱼AI] Port %PORT% already in use, skipping start...
    goto :check_tunnel
)

REM 启动Flask后端(隐藏窗口)
start /B "" "%PYTHON%" app.py > nul 2>&1
echo [沉鱼AI] Backend starting on port %PORT%...

REM 等待后端就绪
timeout /t 3 /nobreak >nul

:check_tunnel
echo [沉鱼AI] Backend service started!
echo [沉鱼AI] Local URL: http://localhost:%PORT%

REM 可选：启动Cloudflare Tunnel(如果需要外网访问)
if exist cloudflared.exe (
    echo [沉鱼AI] Starting Cloudflare Tunnel...
    start /B "" cloudflared.exe tunnel --url http://localhost:%PORT%
    timeout /t 5 /nobreak >nul
    echo [沉鱼AI] Tunnel started! Check console for public URL.
) else (
    echo [沉鱼AI] No cloudflared.exe found. Skipping tunnel.
    echo [沉鱼AI] To enable remote access, download cloudflared.
)

echo [沉鱼AI] === ALL SERVICES READY ===
echo [沉鱼AI] Press any key to exit this window (services keep running)...
pause >nul
