# -*- coding: utf-8 -*-
"""创建v2.3版本的一键启动脚本 + 更新所有快捷方式"""
import os
import subprocess

V23_PATH = r'C:\Users\admin\Desktop\沉鱼AI畅聊助手_v2.3完整版'
SERVER_DIR = os.path.join(V23_PATH, 'server')
START_BAT = os.path.join(V23_PATH, 'start_server.bat')

# 1. 创建启动脚本
bat_content = '''@echo off
chcp 65001 >nul
title 沉鱼AI畅聊助手 v2.3 - 后端服务
echo ============================================
echo   沉鱼AI畅聊助手 v2.3 (返佣系统完整版)
echo   Starting Flask Server on port 5678...
echo ============================================
cd /d "%s"
python app.py
pause
''' % SERVER_DIR

with open(START_BAT, 'w', encoding='utf-8') as f:
    f.write(bat_content)
print('BAT_CREATED:', START_BAT)

# 2. 创建Cloudflare隧道启动脚本
TUNNEL_BAT = os.path.join(V23_PATH, 'start_tunnel.bat')
tunnel_content = '''@echo off
chcp 65001 >nul
title 沉鱼AI畅聊助手 - Cloudflare Tunnel
echo Starting Cloudflare Tunnel...
cd /d "%s"
cloudflared tunnel --url http://localhost:5678
pause
''' % SERVER_DIR
with open(TUNNEL_BAT, 'w', encoding='utf-8') as f:
    f.write(tunnel_content)
print('TUNNEL_BAT_CREATED:', TUNNEL_BAT)

# 3. 创建一键全部启动脚本(后端+隧道)
ALL_BAT = os.path.join(V23_PATH, '一键启动_全部服务.bat')
all_content = '''@echo off
chcp 65001 >nul
title 沉鱼AI畅聊助手 v2.3 - 全部服务
echo.
echo ╔══════════════════════════════════════╗
echo ║  🦞 沉鱼AI畅聊助手 v2.3 完整版       ║
echo ║  返佣+提现+安全加固 全部就绪         ║
echo ╚══════════════════════════════════════╝
echo.

cd /d "%s"

echo [1/2] 启动 Flask 后端服务器...
start "ChenYu-Flask-Backend" cmd /k python app.py

echo [2/2] 等待后端启动后，启动 Cloudflare Tunnel...
timeout /t 3 /nobreak >nul
start "Chenyu-Tunnel" cmd /k cloudflared tunnel --url http://localhost:5678

echo.
echo ✅ 全部服务已启动！
echo    Flask: http://localhost:5678
echo    公网地址请查看 Tunnel 窗口
echo.
echo ⚠️  保持此窗口不关闭 = 服务持续运行
pause
''' % SERVER_DIR
with open(ALL_BAT, 'w', encoding='utf-8') as f:
    f.write(all_content)
print('ALL_IN_ONE_BAT_CREATED:', ALL_BAT)

# 4. 用PowerShell更新桌面快捷方式指向新bat
desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')

ps_script = r'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("%s")
$Shortcut.TargetPath = "%s"
$Shortcut.WorkingDirectory = "%s"
$Shortcut.Description = "沉鱼AI畅聊助手 v2.3 一键启动全部服务"
$Shortcut.IconLocation = "%%SystemRoot%%\\system32\\SHELL32.dll,13"
$Shortcut.Save()
Write-Host "SHORTCUT_UPDATED"
''' % (
    os.path.join(desktop, 'ChenYu-AI-Start-All.lnk'),
    ALL_BAT,
    V23_PATH
)
ps_file = os.path.join(V23_PATH, '_update_shortcut.ps1')
with open(ps_file, 'w', encoding='utf-8') as f:
    f.write(ps_script)

result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file],
                       capture_output=True, text=True)
print('DESKTOP_SHORTCUT:', result.stdout.strip())
if result.stderr and 'HOSTED' not in result.stderr.upper():
    print('ERR:', result.stderr[:200])

# 5. 更新开机自启快捷方式
startup_dir = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows',
                          'Start Menu', 'Programs', 'Startup')
auto_lnk = os.path.join(startup_dir, '沉鱼AI畅聊助手-开机自启.lnk')

ps_auto = '''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("%s")
$Shortcut.TargetPath = "%s"
$Shortcut.WorkingDirectory = "%s"
$Shortcut.Description = "沉鱼AI畅聊助手 v2.3 开机自启"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
Write-Host "AUTO_START_UPDATED"
''' % (auto_lnk, ALL_BAT, V23_PATH)
ps_auto_file = os.path.join(V23_PATH, '_update_autostart.ps1')
with open(ps_auto_file, 'w', encoding='utf-8') as f:
    f.write(ps_auto)

result2 = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_auto_file],
                        capture_output=True, text=True)
print('AUTO_START_SHORTCUT:', result2.stdout.strip())

print('\n=== ALL DONE ===')
print('Default path set to:', V23_PATH)
