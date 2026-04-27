import sys, os, json, urllib.request, ssl, http.client, zipfile, io
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = 'e945691bd452a8b3e95fee51370326af'
BASE_DIR = r'C:\Users\admin\Desktop\AI聊天系统-v1.6.0\server'

# ========== Step 1: 验证 Token + 获取用户信息 ==========
print('=' * 50)
print('  Step 1: 验证 Gitee Token')
print('=' * 50)

req = urllib.request.Request(f'https://gitee.com/api/v5/user?access_token={TOKEN}')
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        user = json.loads(resp.read())
        username = user.get('login', '?')
        print(f'  ✅ 登录成功！用户: {username} (ID: {user.get("id","?")})')
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8', errors='replace')[:200]
    print(f'  ❌ Token无效! HTTP {e.code}: {body}')
    sys.exit(1)
except Exception as e:
    print(f'  ❌ 网络错误: {e}')
    sys.exit(1)

# ========== Step 2: 创建仓库 ==========
print('\n' + '=' * 50)
print('  Step 2: 创建 Gitee 仓库')
print('=' * 50)

conn = http.client.HTTPSConnection('gitee.com', timeout=20)
payload = json.dumps({
    'access_token': TOKEN,
    'name': 'chenyu-ai-chat-server',
    'description': '沉鱼AI畅聊助手后端 v2.1 - Flask+GLM-4-Flash',
    'private': True,
    'auto_init': False
}, ensure_ascii=False).encode('utf-8')

headers = {'Content-Type': 'application/json; charset=utf-8'}
conn.request('POST', '/api/v5/user/repos', body=payload, headers=headers)
resp = conn.getresponse()
data = json.loads(resp.read())

if resp.status in (200, 201):
    repo_full_name = data.get('full_name', f'{username}/chenyu-ai-chat-server')
    repo_html_url = data['html_url']
    print(f'  ✅ 仓库创建成功!')
    print(f'     地址: {repo_html_url}')
    print(f'     私有: {data.get("private")}')
else:
    print(f'  ⚠️ HTTP {resp.status}: {str(data)[:150]}')
    # 尝试获取已有仓库
    req2 = urllib.request.Request(
        f'https://gitee.com/api/v5/user/repos?access_token={TOKEN}&type=owner&page=1&per_page=10&sort=updated'
    )
    try:
        with urllib.request.urlopen(req2, timeout=15) as r:
            repos = json.loads(r.read())
        repo_html_url = None
        for rp in repos:
            name = rp.get('name', '')
            if 'chenyu' in name.lower() or 'ai-chat' in name.lower():
                repo_html_url = rp['html_url']
                repo_full_name = rp['full_name']
                print(f'  ✅ 使用已有仓库: {repo_html_url}')
                break
        if not repo_html_url:
            print('  ❌ 无法创建或找到仓库!')
            sys.exit(1)
    except Exception as e:
        print(f'  ❌ 查询失败: {e}')
        sys.exit(1)

# ========== Step 3: 上传代码文件 ==========
print('\n' + '=' * 50)
print('  Step 3: 上传代码到 Gitee')
print('=' * 50)

# 要上传的文件列表
upload_files = [
    ('app.py', 'application/python'),
    ('requirements.txt', 'text/plain'),
    ('Procfile', 'text/plain'),
    ('render.yaml', 'text/yaml'),
    ('README.md', 'text/markdown'),
]

# 先读取所有文件内容
file_contents = {}
for fname, _ in upload_files:
    fpath = os.path.join(BASE_DIR, fname)
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            file_contents[fname] = f.read()
        print(f'  📄 已读取: {fname} ({len(file_contents[fname])} bytes)')
    else:
        print(f'  ❌ 文件不存在: {fpath}')

# 获取默认分支（Gitee创建后自动有master分支）
branch_req = urllib.request.Request(
    f'https://gitee.com/api/v5/repos/{repo_full_name}/branches/master?access_token={TOKEN}'
)
try:
    with urllib.request.urlopen(branch_req, timeout=10) as br:
        branch_data = json.loads(br.read())
        master_sha = branch_data.get('commit', {}).get('sha', '')
        print(f'  📌 Master SHA: {master_sha[:12]}...')
except:
    master_sha = ''

uploaded_count = 0
for fname, content_type in upload_files:
    if fname not in file_contents:
        continue
    
    content = file_contents[fname]
    
    # 构造 API URL
    import base64
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
    
    api_url = f'https://gitee.com/api/v5/repos/{repo_full_name}/contents/{fname}?access_token={TOKEN}'
    
    payload = json.dumps({
        'content': encoded_content,
        'message': f'add {fname} - deploy for ChenYu AI v2.1',
        'branch': 'master'
    }, ensure_ascii=False).encode('utf-8')
    
    req3 = urllib.request.Request(api_url, data=payload, method='POST',
                                  headers={'Content-Type': 'application/json; charset=utf-8'})
    
    try:
        with urllib.request.urlopen(req3, timeout=30) as r:
            result = json.loads(r.read())
            print(f'  ✅ 上传成功: {fname} → {result.get("content", {}).get("html_url", "ok")}')
            uploaded_count += 1
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')[:200]
        print(f'  ⚠️ {fname} 上传失败 (HTTP {e.code}): {err_body}')

# ========== 完成 ==========
print('\n' + '=' * 50)
print(f'  部署结果: {uploaded}/{len(upload_files)} 个文件上传成功')
if uploaded_count >= len([f for f,_ in upload_files if f in file_contents]):
    print(f'\n  ✅ 所有文件上传完成!')
    print(f'  🔗 仓库地址: {repo_html_url}')
else:
    print(f'\n  ⚠️ 部分文件未成功，请检查')
print('=' * 50)
