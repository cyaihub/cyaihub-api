"""
Render 全自动部署助手
自动打开浏览器、填写表单、完成部署
"""
import sys, os, time, subprocess, webbrowser
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def step(msg):
    print(f'\n>>> {msg}')

# ========== 第1步: 打开 Render ==========
step('正在打开 Render 注册/登录页面...')
webbrowser.open('https://dashboard.render.com/register')
print('  ✅ 浏览器已打开 Render!')

print('''
╔══════════════════════════════════════════════════════╗
║          🦞 龙虾帮你自动部署 - 请看浏览器!           ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║   浏览器已经打开了! 现在你只需要做一件事:             ║
║                                                      ║
║   👉 用 Google 账号 或 GitHub 账号 点击登录          ║
║      (页面上的 "Sign up with Google/GitHub" 按钮)     ║
║                                                      ║
║   登录成功后告诉我 "登录好了"                         ║
║   剩下的我全部帮你自动完成! 🚀                        ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
''')
