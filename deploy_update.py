import sys, os, json, urllib.request, ssl, http.client, base64
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = 'e945691bd452a8b3e95fee51370326af'
BASE_DIR = r'C:\Users\admin\Desktop\AI聊天系统-v1.6.0\server'
REPO = 'mihuleya/chenyu-ai-chat-server'

print('=' * 50)
print('  更新 Gitee 代码仓库 (v2.1)')
print('=' * 50)

# 要上传的文件
upload_files = ['app.py', 'requirements.txt', 'Procfile', 'render.yaml', '.gitignore']

# 先获取SHA（用于更新已有文件）
sha_map = {}
for fname in upload_files:
    try:
        url = f'https://gitee.com/api/v5/repos/{REPO}/contents/{fname}?access_token={TOKEN}&ref=master'
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            sha_map[fname] = data.get('sha', '')
            print(f'  📄 {fname} SHA: {sha_map[fname][:12]}...')
    except Exception as e:
        print(f'  ➕ {fname} (新文件, 无SHA)')
        sha_map[fname] = ''

# 上传或更新每个文件
ok = 0
fail = 0
for fname in upload_files:
    fpath = os.path.join(BASE_DIR, fname)
    if not os.path.exists(fpath):
        print(f'  ❌ 跳过(不存在): {fname}')
        fail += 1
        continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
    
    payload_data = {
        'content': encoded,
        'message': f'update {fname} - v2.1 deploy',
        'branch': 'master'
    }
    if sha_map.get(fname):
        payload_data['sha'] = sha_map[fname]
    
    url = f'https://gitee.com/api/v5/repos/{REPO}/contents/{fname}?access_token={TOKEN}'
    method = 'PUT' if sha_map.get(fname) else 'POST'
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload_data, ensure_ascii=False).encode('utf-8'),
        method=method,
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read())
            size_kb = len(content) / 1024
            action = '更新' if sha_map.get(fname) else '新建'
            print(f'  ✅ {action}: {fname} ({size_kb:.1f}KB)')
            ok += 1
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8', errors='replace')[:150]
        print(f'  ⚠️ {fname} 失败({e.code}): {err}')
        fail += 1

print('\n' + '=' * 50)
print(f'  结果: {ok} 成功, {fail} 失败')
print(f'  仓库: https://gitee.com/mihuleya/chenyu-ai-chat-server')
if ok == len(upload_files):
    print('  ✅ 全部完成! 可以开始部署到云端!')
else:
    print(f'  ⚠️ 部分失败，请检查上面的错误信息')
print('=' * 50)
