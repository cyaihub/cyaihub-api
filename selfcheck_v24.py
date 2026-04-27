# -*- coding: utf-8 -*-
"""v2.4 第1轮+第2轮全面自检"""
import os, py_compile

BASE = r'C:\Users\admin\Desktop\沉鱼AI畅聊助手_v2.3完整版'
app_py = os.path.join(BASE, 'server', 'app.py')

print('=' * 60)
print('  V2.4 COMPREHENSIVE SELF-CHECK (Round 1)')
print('=' * 60)

# 1. 语法
try:
    py_compile.compile(app_py, doraise=True)
    print('[PASS] app.py syntax OK')
except Exception as e:
    print('[FAIL] syntax:', e)

with open(app_py, 'r', encoding='utf-8') as f:
    c = f.read()

checks = [
    ('[P0] wx_login invite_code', "invite_code = data.get('invite_code'" in c),
    ('[P0] wx_login inviter_id INSERT', 'inviter_id, free_count' in c.split("def wx_login")[1].split("def ")[0]),
    ('[P0] commissions DDL', 'CREATE TABLE IF NOT EXISTS commissions' in c),
    ('[P0] withdrawals DDL', 'CREATE TABLE IF NOT EXISTS withdrawals' in c),
    ('[P0] auto commission on approve', 'INSERT INTO commissions' in c),
    ('[P0] real SUM query', 'SUM(commission_amount)' in c),
    ('[P0] withdraw API', '/api/user/withdraw' in c),
    ('[P0] admin review withdraw', '/api/admin/withdraw/review' in c),
    ('[FIX1] dashboard loadProfile inviteInfo', None),  # check js
    ('[FIX2a] team SQL is_vip', 'is_vip' in c and 'SELECT username, nickname, created_at, CASE WHEN is_vip' in c),
    ('[FIX2b] link field', "'link': " in c),
    ('[FIX2b] team field', "'team':" in c),
    ('[FIX2b] commissions format', 'commission_amount' in c),
    ('[FIX3] privacy page exists', os.path.exists(os.path.join(BASE, 'pages','privacy','privacy.js'))),
    ('[FIX4] terms page exists', os.path.exists(os.path.join(BASE, 'pages','terms','terms.js'))),
    ('[FIX5] pages registered', '"pages/privacy/privacy"' in open(os.path.join(BASE,'app.json'),'r',encoding='utf-8').read()),
    ('[FIX6] version v2.4', 'v2.4' in c or '2.4.0' in c),
]

passed = 0
failed = 0
for name, ok in checks:
    if ok is None:
        # JS file checks
        dash_js = os.path.join(BASE,'pages','dashboard','dashboard.js')
        content = open(dash_js,'r',encoding='utf-8').read()
        ok_dash = 'getInviteInfo' in content
        if '[FIX1]' in name:
            ok = ok_dash
        else:
            ok = True
    
    status = 'PASS' if ok else 'FAIL'
    if not ok:
        failed += 1
    else:
        passed += 1
    print(f'  {status} {name}')

print(f'\n--- Round 1 Result: {passed}/{len(checks)} PASS ---')
if failed > 0:
    print(f'!!! {failed} items FAILED - need fix !!!')
else:
    print('ALL CHECKS PASSED! Ready for Round 2.')
