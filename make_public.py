import sys, json, urllib.request, ssl
sys.stdout.reconfigure(encoding='utf-8')
ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = 'e945691bd452a8b3e95fee51370326af'
REPO = 'mihuleya/chenyu-ai-chat-server'

print('正在将 Gitee 仓库改为公开...')

# Gitee API: 编辑仓库信息
import http.client
conn = http.client.HTTPSConnection('gitee.com', timeout=15)

payload = json.dumps({
    'access_token': TOKEN,
    'name': 'chenyu-ai-chat-server',
    'description': '沉鱼AI畅聊助手后端 v2.1 - Flask+GLM-4-Flash',
    'private': False,  # 改成公开！
    'has_issues': True,
    'has_wiki': False
}, ensure_ascii=False).encode('utf-8')

headers = {'Content-Type': 'application/json; charset=utf-8'}
conn.request('PATCH', f'/api/v5/repos/{REPO}', body=payload, headers=headers)
resp = conn.getresponse()
data = json.loads(resp.read())

if resp.status == 200:
    print(f'✅ 成功! 仓库已改为: {"私有" if data["private"] else "公开"}')
    print(f'   地址: {data["html_url"]}')
else:
    print(f'⚠️ HTTP {resp.status}: {str(data)[:200]}')

conn.close()
