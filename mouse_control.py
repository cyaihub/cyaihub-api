"""
🦞 龙虾全自动鼠标控制部署器
自动帮用户在Render上点击完成部署
"""
import sys, time, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import pyautogui
import pyperclip
from PIL import ImageGrab

pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'  [{ts}] {msg}')

def screenshot(name=''):
    img = ImageGrab.grab()
    path = rf'C:\Users\admin\Desktop\AI聊天系统-v1.6.0\server\screen_{name}.png'
    img.save(path)
    return path

def click(x, y, desc=''):
    log(f'点击: {desc} @ ({x},{y})')
    pyautogui.click(x, y)
    time.sleep(1)

def type_text(text):
    pyperclip.copy(text)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)

print('=' * 50)
print('  🦞 龙虾全自动鼠标控制器 v2')
print('  不要动鼠标键盘，龙虾在操作!')
print('=' * 50)

# 先截图看当前状态
log('截取当前屏幕...')
screenshot('start')
print(f'  截图已保存')
print()
print('📍 当前屏幕已截图，龙虾正在分析位置...')
print()

# 根据截图分析：用户已在Render页面
# "Add new..." 按钮大约在顶部导航栏的 (910, 18) 附近
# 让我们点击它

log('正在点击 "Add new..." 按钮...')
click(910, 18, 'Add new')
time.sleep(2)

screenshot('after_addnew')

# 现在应该出现下拉菜单，选择 Web Service
log('等待菜单出现...')

input('  看到菜单了吗？按Enter继续，或告诉龙虾你看到的 >> ')

# 继续操作...
print('\n✅ 第一步完成! 继续...')
