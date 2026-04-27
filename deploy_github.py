# -*- coding: utf-8 -*-
"""
沉鱼AI畅聊助手 - 全自动云端部署脚本
使用 GitHub API 创建仓库 + 上传代码
只需要一个 GitHub Personal Access Token
"""
import sys
import os
import json
import base64
import requests
import time

sys.stdout.reconfigure(encoding='utf-8')

GITHUB_API = 'https://api.github.com'

def deploy(token, repo_name='chenyu-ai-backend', private=True):
    """一键部署：创建仓库 + 上传所有文件"""
    
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ChenYu-AI-Deploy/1.0'
    }
    
    # 验证token
    print('[1/4] Verifying GitHub token...')
    r = requests.get(f'{GITHUB_API}/user', headers=headers)
    if r.status_code != 200:
        print(f'  ERROR: Token invalid! Status {r.status_code}')
        print(f'  Response: {r.text[:200]}')
        return None
    user = r.json()['login']
    print(f'  OK! Logged in as: {user}')
    
    # Step 1: Create repository
    print(f'\n[2/4] Creating repository: {repo_name}...')
    repo_data = {
        'name': repo_name,
        'description': '沉鱼AI畅聊助手后端服务 v2.1 - Flask + GLM-4-Flash AI',
        'private': private,
        'has_issues': False,
        'has_wiki': False,
        'has_projects': False,
        'auto_init': False
    }
    r = requests.post(f'{GITHUB_API}/user/repos', headers=headers, json=repo_data)
    if r.status_code == 201:
        print(f'  OK! Repo created: {r.json()["html_url"]}')
        repo_url = r.json()["html_url"]
    elif r.status_code == 422 and 'already exists' in r.text:
        print(f'  Repo already exists, reusing it')
        repo_url = f'https://github.com/{user}/{repo_name}'
    else:
        print(f'  ERROR creating repo: {r.status_code} - {r.text[:200]}')
        return None
    
    # Step 2: Get default branch
    time.sleep(1)
    r = requests.get(f'{GITHUB_API}/repos/{user}/{repo_name}', headers=headers)
    default_branch = r.json().get('default_branch', 'main')
    print(f'  Default branch: {default_branch}')
    
    # Step 3: Upload files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files_to_upload = {
        'app.py': 'Main Flask backend (v2.1, ~1200 lines, 18 APIs)',
        'requirements.txt': 'Python dependencies (flask, openai, jwt, etc.)',
        'Procfile': 'Render startup command',
        'render.yaml': 'Render cloud deployment config',
        '.gitignore': 'Ignore rules for cloud deployment',
    }
    
    print(f'\n[3/4] Uploading {len(files_to_upload)} files...')
    
    for filename, desc in files_to_upload.items():
        filepath = os.path.join(base_dir, filename)
        if not os.path.exists(filepath):
            print(f'  ⚠️ SKIP: {filename} (not found)')
            continue
        
        with open(filepath, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        
        file_data = {
            'message': f'Add {filename} - v2.1 deployment',
            'content': content,
            'branch': default_branch
        }
        
        api_url = f'{GITHUB_API}/repos/{user}/{repo_name}/contents/{filename}'
        r = requests.put(api_url, headers=headers, json=file_data)
        
        if r.status_code in (200, 201):
            sha = r.json().get('content', {}).get('sha', '')[:7]
            print(f'  ✅ {filename} ({desc}) [sha:{sha}]')
        else:
            print(f'  ❌ {filename} ERROR: {r.status_code}')
    
    # Step 4: Verify
    print(f'\n[4/4] Verifying deployment...')
    time.sleep(1)
    r = requests.get(f'{GITHUB_API}/repos/{user}/{repo_name}/contents/', headers=headers)
    uploaded_files = [f['name'] for f in r.json()]
    print(f'  Files on GitHub: {", ".join(uploaded_files)}')
    
    print('\n' + '=' * 50)
    print('  🎉 GITHUB DEPLOYMENT COMPLETE!')
    print('=' * 50)
    print(f'  Repository: {repo_url}')
    print(f'  Owner: {user}')
    print(f'  Next step: Go to https://dashboard.render.com')
    print(f'           Connect this repo and deploy!')
    print('=' * 50)
    
    return {'user': user, 'repo': repo_name, 'url': repo_url}


if __name__ == '__main__':
    print('=' * 50)
    print('  ChenYu AI Auto Deploy Tool')
    print('=' * 50)
    
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        print('\nUsage: python deploy_github.py <YOUR_GITHUB_TOKEN>')
        print()
        print('To get a token:')
        print('  1. Go to https://github.com/settings/tokens/new')
        print('  2. Click "Generate new token (classic)"')
        print('  3. Check "repo" scope only')
        print('  4. Generate and copy the token')
        print()
        token = input('Paste your GitHub token here: ').strip()
    
    if not token:
        print('ERROR: No token provided!')
        sys.exit(1)
    
    result = deploy(token)
    if result:
        print(f'\nDone! Repo: {result["url"]}')
