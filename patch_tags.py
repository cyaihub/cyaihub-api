# -*- coding: utf-8 -*-
import re

APP_FILE = 'app.py'
with open(APP_FILE, 'r', encoding='utf-8') as f:
    c = f.read()

new_func = '''
def _parse_v3_replies_tagged(raw):
    """v3.1增强版解析-保留策略标签 返回[{text,tag},...]"""
    import re
    results = []
    for line in raw.split(chr(10)):
        line = line.strip()
        if not line:
            continue
        tag = ''
        text = line
        tm = re.match(r'^\[([^\]]+)\]\s*(.+)$', line)
        if tm:
            tag = tm.group(1).strip()
            text = tm.group(2).strip()
        for p in [f'{i}.' for i in range(1, 30)] + [f'{i}\u3001' for i in range(1, 30)] + [f'{i})' for i in range(1, 30)] + ['-', '*', '\u00b7']:
            if text.startswith(p):
                text = text[len(p):].strip()
        for q in ['\u201c', '\u201d', '\u2018', '\u2019']:
            if text.startswith(q):
                text = text[1:].strip()
            if text.endswith(q):
                text = text[:-1].strip()
        if text and len(text) >= 2:
            results.append({'text': text, 'tag': tag})
    return results


'''

marker = 'def _generate_variants(base_reply, count=15):'
if marker not in c:
    print('ERROR: marker not found')
else:
    idx = c.find(marker)
    c = c[:idx] + new_func + c[idx:]
    
    # Modify call_ai_api to use tagged parser
    old = 'replies = _parse_v3_replies(raw)'
    new_code = '''pt = _parse_v3_replies_tagged(raw)
        if pt:
            replies = [x["text"] for x in pt]
            g.tagged_replies = pt
        else:
            replies = _parse_v3_replies(raw)
            g.tagged_replies = None'''
    if old in c:
        c = c.replace(old, new_code)
        print('OK: call_ai_api updated')
    else:
        print('WARN: parse code not found (may already be updated)')
    
    # Add suggestion_tags to API response
    old2 = "'suggestions': suggestions,\n                'remaining_free':"
    new2 = "'suggestions': suggestions,\n                'suggestion_tags': getattr(g,'tagged_replies',None),\n                'remaining_free':"
    if old2 in c:
        c = c.replace(old2, new2)
        print('OK: API response has tags field')
    else:
        print('WARN: API return not found')
    
    with open(APP_FILE, 'w', encoding='utf-8') as f:
        f.write(c)
    
    import py_compile
    py_compile.compile(APP_FILE, doraise=True)
    print('OK: Syntax check passed!')
    print('DONE - Strategy tags system installed!')
