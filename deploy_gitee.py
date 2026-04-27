# -*- coding: utf-8 -*-
"""
沉鱼AI畅聊助手 - 全自动云端部署 v3（Gitee版）
国内直连，无需翻墙！
"""
import sys, os, json, time, base64, requests
sys.stdout.reconfigure(encoding='utf-8')

GITEE_API = 'https://gitee.com/api/v5'

def deploy_gitee(token, repo_name='chenyu-ai-backend'):
    """一键部署到Gitee"""
    headers = {'Content-Type': 'application/json'}
    params = {'access_token': token}
    
    # Get user info
    print('[1/4] Verifying token...')
    r = requests.get(f'{GITEE_API}/user', params=params, timeout=15)
    if r.status_code != 200:
        print(f'  Token invalid: {r.status_code} - {r.text[:200]}')
        return None
    user = r.json()['login']
    print(f'  OK! Account: {user}')
    
    # Create repo
    print(f'[2/4] Creating repository...')
    repo_data = {
        'access_token': token,
        'name': repo_name,
        'description': 'ChenYu AI Chat Backend v2.1 | Flask + GLM-4-Flash',
        'private': True,
        'auto_init': False,
    }
    r = requests.post(f'{GITEE_API}/user/repos', data=repo_data, timeout=30)
    if r.status_code == 201:
        print(f'  Repo created! {r.json().get("html_url", "")} ✅')
    elif 'already exists' in str(r.content).lower() or r.status_code == 400 or r.status_code == 409:
        print(f'  Repo exists, reusing ✅')
    else:
        print(f'  Warning: {r.status_code} - continuing anyway')
    
    # Upload files via Gitee API
    print(f'[3/4] Uploading files...')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files = {
        'app.py': 'Main Flask backend v2.1',
        'requirements.txt': 'Python dependencies',
        'Procfile': 'Render/Koyeb startup',
        '.gitignore': 'Ignore rules',
    }
    
    for fname, desc in files.items():
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            continue
        
        with open(fpath, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
        
        file_params = {
            'access_token': token,
            'content': content,
            'message': f'add {fname} v2.1 deploy',
        }
        
        url = f'{GITEE_API}/repos/{user}/{repo_name}/contents/{fname}'
        r = requests.post(url, data=file_params, timeout=30)
        status = 'OK' if r.status_code == 201 else f'{r.status_code}'
        print(f'  [{status}] {fname} - {desc}')
    
    repo_url = f'https://gitee.com/{user}/{repo_name}'
    
    # Clone URL for deployment
    clone_url = f'https://gitee.com/{user}/{repo_name}.git'
    
    print(f'\n[4/4] Done!')
    print('=' * 50)
    print(f'  Gitee Repository: {repo_url}')
    print(f'  Git Clone URL: {clone_url}')
    print('=' * 50)
    
    return {
        'user': user,
        'repo': repo_name,
        'url': repo_url,
        'clone_url': clone_url,
    }


def get_gitee_token_guide():
    """Print instructions for getting Gitee token"""
    print("""
╔════════════════════════════════════════════╗
║  获取 Gitee 私人令牌 (30秒搞定)           ║
╚══════════════════════════════════════════╝

  Step 1: 浏览器打开 (应该能正常加载):
           https://gitee.com/login
  
  Step 2: 登录你的Gitee账号
           (没有就免费注册一个，10秒)
  
  Step 3: 打开令牌页面:
           https://gitee.com/profile/personal_access_tokens
  
  Step 4: 点击 "生成新令牌"
           - 描述填: ChenYu-AI-Deploy
           - 权限勾选: projects ✓
           - 点提交
  
  Step 5: 复制生成的Token (以 gitee_ 开头)
           发给龙虾！
""")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        token = sys.argv[1]
        result = deploy_gitee(token)
        if result:
            print('\n🎉 Ready for cloud deployment!')
    else:
        get_gitee_token_guide()
        token = input('\nPaste your Gitee token here: ').strip()
        if token:
            deploy_gitee(token)
