# -*- coding: utf-8 -*-
import py_compile, re

py_compile.compile('app.py', doraise=True)
print('OK Syntax check passed')

with open('app.py','r',encoding='utf-8') as f:
    c = f.read()

checks = [
    ('v3.1 identity: friend', "'friend'"),
    ('v3.1 identity: chase', "'chase'"),
    ('v3.1 identity: couple', "'couple'"),
    ('v3.1 identity: funny', "'funny'"),
    ('v3.1 identity: gentle', "'gentle'"),
    ('v3.1 marketing: lead', "'lead'"),
    ('v3.1 marketing: follow', "'follow'"),
    ('v3.1 marketing: close', "'close'"),
    ('v3.1 marketing: service', "'service'"),
    ('v3.1 marketing: complaint', "'complaint'"),
    ('target_info in prompt', 'target_info'),
    ('emotion analysis', '\u60c5\u7eea\u5206\u6790'),
    ('tagged parser', '_parse_v3_replies_tagged'),
    ('tagged_replies var', 'tagged_replies'),
    ('temp 0.88', 'temperature=0.88'),
    ('top_p 0.92', 'top_p=0.92'),
    ('variant v2', '\u8bed\u4e49\u53d8\u6362'),
]

print()
for name, pat in checks:
    found = pat in c
    s = 'OK' if found else 'FAIL'
    print(f'  [{s}] {name}')

print(f'\n  Lines: {len(c.split(chr(10)))}, Size: {len(c):,}')
