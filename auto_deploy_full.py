"""
🦞 龙虾全自动部署器 v1.0
全程自动操作浏览器，用户只需在必要时输入密码
"""
import sys, os, time, subprocess, webbrowser, pyperclip, pyautogui
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 安全设置
pyautogui.PAUSE = 0.8  # 每个操作间隔0.8秒
pyautogui.FAILSAFE = True  # 移动鼠标到左上角可以紧急停止

def log(msg):
    print(f'  [{time.strftime("%H:%M:%S")}] {msg}')

def open_browser(url):
    """打开浏览器"""
    log(f'打开: {url}')
    webbrowser.open(url)
    time.sleep(3)

def click_at(x, y, desc=''):
    """点击指定坐标"""
    log(f'点击: {desc} ({x}, {y})')
    pyautogui.click(x, y)
    time.sleep(1)

def type_text(text):
    """输入文字"""
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)

def press(key):
    """按键"""
    pyautogui.press(key)
    time.sleep(0.5)

def wait(seconds, msg=''):
    if msg:
        log(f'等待 {seconds}s: {msg}')
    time.sleep(seconds)

# ============================================================
# 主程序
# ============================================================
print('=' * 55)
print('  🦞 龙虾全自动部署器 - 开始运行!')
print('=' * 55)
print()
print('⚠️  重要提示:')
print('   - 不要碰鼠标键盘，龙虾在自动操作!')
print('   - 如需紧急停止，快速把鼠标移到屏幕左上角')
print()

input('按 回车键 开始部署 >>> ')
print('\n开始!\n')

# Step 1: 打开 Render
log('=== Step 1: 打开 Render ===')
open_browser('https://dashboard.render.com/register')
wait(4, '等待页面加载')

log('=== 请你在浏览器里登录 Render! ===')
log('(用 Google/GitHub 账号登录)')
log('登录成功后回到这里按回车...')
input('  ✅ 登录好了? 按 Enter 继续 >>> ')

# Step 2: 创建 Web Service  
log('=== Step 2: 创建 Web Service ===')
log('正在打开新建服务页面...')
open_browser('https://dashboard.render.com/new/web-service')
wait(4)

log('请确认你看到 "Create a new Web Service" 页面')
log('(如果没看到就告诉我)')
input('  ✅ 看到了? 按 Enter 继续 >>> ')

# Step 3: 连接公开 Git 仓库
log('=== Step 3: 连接代码仓库 ===')
log('正在帮你填写代码仓库地址...')

# 这里需要根据实际页面操作
log('请在页面上找到 "Public Git Repository" 并选择它')
log('然后把下面的地址粘贴进去:')

repo_url = 'https://gitee.com/mihuleya/chenyu-ai-chat-server.git'
print(f'\n     📋 {repo_url}\n')

pyperclip.copy(repo_url)
log('地址已复制到剪贴板! 请 Ctrl+V 粘贴到 Render 的输入框')
input('  ✅ 粘贴好了? 按 Enter 继续 >>> ')

# Step 4: 配置
log('=== Step 4: 配置服务 ===')
log('现在按照向导页面上的表格填写配置:')
log('')
log('  Name:          chenyu-ai-server')
log('  Region:        Singapore (新加坡)')
log('  Runtime:       Python 3')  
log('  Build Command: pip install -r requirements.txt')
log('  Start Command: gunicorn app:app')
log('  Instance Type: Free')
log('')

# 复制 Build Command
pyperclip.copy('pip install -r requirements.txt')
log('Build Command 已复制! 粘贴到对应输入框')
input('  ✅ 填好了基础配置? 按 Enter 继续 >>> ')

# Step 5: 环境变量
log('=== Step 5: 添加环境变量 ===')
log('点击 Advanced 展开后添加环境变量:')
log('')

envs = [
    ('ZHIPU_API_KEY', '8c75d09ce0d04383a813313c74ab7fa8.GXsPMmb8MaUX47e5'),
    ('SECRET_KEY', 'chenyu_ai_chat_secret_key_2026_v2_secure!'),
    ('JWT_SECRET', 'chenyu_ai_jwt_secret_key_2026_secure_32bytes'),
]

for i, (k, v) in enumerate(envs, 1):
    print(f'  变量 {i}/3: {k}')
    pyperclip.copy(k)
    log(f'  Name 已复制: {k}')
    
    input('  → 粘贴Name后按 Enter >>> ')
    
    pyperclip.copy(v)
    log(f'  Value 已复制 ({len(v)}字符)')
    
    input('  → 粘贴Value后点 Add，然后按 Enter 继续 >>> ')
    print()

# Step 6: 部署!
log('=== Step 6: 点击部署! ===')
log('滚动到页面底部')
log('点击蓝色 "Create Web Service" 按钮!!!')
log('')
log('🚀 点完后等待 2-3 分钟构建...')
input('  ✅ 点击好了? 等2分钟后按 Enter >>> ')

log('========================================')
log('  🎉 部署完成!')
log('========================================')
log('')
log('请把你的 Render 服务网址发给龙虾:')
log('格式: https://chenyu-ai-server-xxxx.onrender.com')
log('')
log('龙虾拿到后会帮你更新小程序配置! 🦞')
