# -*- coding: utf-8 -*-
"""补丁：添加link和team字段"""
fp = r'C:\Users\admin\Desktop\沉鱼AI畅聊助手_v2.3完整版\server\app.py'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

old = """'commissions': [dict(c) for c in commission_list],
        'invited_users': invite_users
    }"""

new = """'link': 'pages/register/register?invite_code=' + user['invite_code'],
        'team': invite_users,
        'commissions': [{'id':x['id'],'amount':x.get('commission_amount',0),'status':x.get('status','pending'),'plan_type':x.get('plan_type',''),'created_at':x.get('created_at'),'buyer_name':x.get('buyer_name','')} for x in commission_list],
        'invited_users': invite_users
    }"""

if old in c:
    c = c.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)
    print('PATCH_OK: link+team+commissions格式修复')
else:
    print('SKIP: pattern not found')
