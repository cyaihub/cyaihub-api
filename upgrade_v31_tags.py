# -*- coding: utf-8 -*-
"""
v3.1 补丁升级: 策略标签透传系统
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(BASE_DIR, 'app.py')

print('=' * 60)
print('  v3.1 补丁: 策略标签透传系统')
print('=' * 60)

with open(APP_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

changes = []

# ============================================================
# 1. 新增带标签的解析函数
# ============================================================
new_parser = '''
def _parse_v3_replies_tagged(raw):
    """v3.1增强版解析 - 保留策略标签，返回结构化数据
    
    Returns:
        list of dict: [{text: str, tag: str}, ...]
    """
    import re
    results = []
    for line in raw.split('\\n'):
        line = line.strip()
        if not line:
            continue
        
        tag = ''
        text = line
        
        tag_match = re.match(r'^\\[([^\\]]+)\\]\\s*(.+)$', line)
        if tag_match:
            tag = tag_match.group(1).strip()
            text = tag_match.group(2).strip()
        
        for prefix in [f'{i}.' for i in range(1, 30)] + [f'{i}\u3001' for i in range(1, 30)] + \\
                     [f'{i})' for i in range(1, 30)] + ['-', '*', '\u00b7', '\u1830']:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        for q in ['\u201c', '\u201d', '\u2018', '\u2019', '"']:
            if text.startswith(q): text = text[1:].strip()
            if text.endswith(q): text = text[:-1].strip()
        
        if text and len(text) >= 2:
            results.append({'text': text, 'tag': tag})
    
    return results


'''

insert_marker = '    return replies\n\n\n\n\ndef _generate_variants'
if insert_marker in content:
    content = content.replace(insert_marker, '    return replies\n' + new_parser + '\ndef _generate_variants')
    changes.append('OK 新增 _parse_v3_replies_tagged 函数')
else:
    changes.append('WARN 未找到插入点')

# ============================================================
# 2. 修改 call_ai_api
# ============================================================
old_parse = '''raw = response.choices[0].message.content.strip()
        
        replies = _parse_v3_replies(raw)'''

new_parse = '''raw = response.choices[0].message.content.strip()
        
        parsed_tagged = _parse_v3_replies_tagged(raw)
        if parsed_tagged:
            replies = [item['text'] for item in parsed_tagged]
            g.tagged_replies = parsed_tagged
        else:
            replies = _parse_v3_replies(raw)
            g.tagged_replies = None'''

if old_parse in content:
    content = content.replace(old_parse, new_parse)
    changes.append('OK call_ai_api 使用带标签解析')

# ============================================================
# 3. API增加suggestion_tags字段
# ============================================================
old_return = "'suggestions': suggestions,\n                'remaining_free': remaining['free_count'],"
new_return = """'suggestions': suggestions,
                'suggestion_tags': getattr(g, 'tagged_replies', None),
                'remaining_free': remaining['free_count'],"""

if old_return in content:
    content = content.replace(old_return, new_return)
    changes.append('OK API响应增加 suggestion_tags 字段')

# ============================================================
# 写回 + 验证
# ============================================================
with open(APP_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\n 变更清单 ({len(changes)}项):')
for i,c in enumerate(changes,1):
    print(f'  {i}. {c}')

import py_compile
try:
    py_compile.compile(APP_FILE, doraise=True)
    print('\n OK 语法检查通过!')
except py_compile.PyCompileError as e:
    print(f'\n ERROR: {e}')

print('=' * 60)
print('  v3.1 策略标签补丁完成!')
print('=' * 60)
