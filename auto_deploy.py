# -*- coding: utf-8 -*-
"""
沉鱼AI畅聊助手 - 全自动云端部署工具 v2
使用 GitHub Device Flow (无需电脑浏览器!)
只需要用手机授权即可!
"""
import sys, os, json, time, base64, requests, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

GITHUB_API = 'https://api.github.com'
CLIENT_ID = 'Ov23liqJbP9HhA6xZvwk'  # GitHub App client_id for device flow

def step1_request_device_code():
    """Step 1: 请求设备码 - 给用户一个code去手机上输入"""
    print('=' * 55)
    print('  Step 1: Requesting GitHub Device Code...')
    print('=' * 55)
    
    data = {
        'client_id': CLIENT_ID,
        'scope': 'repo',
    }
    r = requests.post(f'{GITHUB_API}/login/device/code', json=data, timeout=30)
    if r.status_code != 200:
        print(f'ERROR: {r.status_code} - {r.text[:300]}')
        return None
    
    result = r.json()
    print('\n' + '🔑' * 27)
    print('   ⚠️  请立即拿出你的手机!')
    print('🔑' * 27)
    print(f'\n   1️⃣  手机浏览器打开:\n       {result["verification_uri"]}\n')
    print(f'   2️⃣  输入这个代码:\n       📱 {result["user_code"]} 📱\n')
    print(f'   3️⃣  点击 "Authorize" 授权\n')
    print('   (代码有效期: %d 秒, 请尽快操作)' % result.get('interval', 5))
    print('')
    return result


def step2_wait_for_token(device_code, interval=5):
    """Step 2: 轮询等待用户在手机上授权"""
    print('=' * 55)
    print('  Step 2: Waiting for your authorization...')
    print('  (请在手机上完成上面的步骤)')
    print('=' * 55)
    
    data = {
        'client_id': CLIENT_ID,
        'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
    }
    
    max_attempts = 60  # 最多等5分钟
    for i in range(max_attempts):
        time.sleep(interval)
        r = requests.post(f'{GITHUB_API}/login/oauth/access_token', json=data, timeout=30)
        
        if r.status_code == 200:
            token_data = r.json()
            if 'access_token' in token_data:
                print('\n✅ AUTHORIZATION SUCCESS!\n')
                return token_data['access_token']
            elif token_data.get('error') == 'authorization_pending':
                dots = '.' * ((i % 4) + 1)
                print(f'\r   Waiting{dots:<4} ({i*interval}s)', end='', flush=True)
                continue
            elif token_data.get('error') == 'slow_down':
                interval += 5
                print('\n  Slow down, increasing polling interval...')
                continue
            else:
                print(f'\n  Error: {token_data}')
                return None
        else:
            print(f'\n  HTTP Error: {r.status_code}')
            return None
    
    print('\n\n⏰ Timeout! Please try again.')
    return None


def step3_create_repo_and_upload(token, repo_name='chenyu-ai-backend'):
    """Step 3: 自动创建仓库并上传全部代码"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'Time-Zone': 'Asia/Shanghai',
    }
    
    # Get user info
    print('[3/5] Getting account info...')
    r = requests.get(f'{GITHUB_API}/user', headers=headers, timeout=15)
    if r.status_code != 200:
        print(f'  ERROR: {r.text[:200]}')
        return None
    user = r.json()['login']
    print(f'  Account: {user}')
    
    # Create repo
    print(f'[4/5] Creating repository: {repo_name} ...')
    repo_data = {
        'name': repo_name,
        'description': 'ChenYu AI Chat Backend v2.1 | Flask + GLM-4-Flash',
        'private': True,
        'auto_init': False,
    }
    r = requests.post(f'{GITHUB_API}/user/repos', headers=headers, json=repo_data, timeout=30)
    if r.status_code == 201:
        print(f'  Repo created! ✅')
    elif r.status_code == 422:
        print(f'  Repo already exists, reusing it ✅')
    else:
        print(f'  WARNING: {r.status_code} - trying anyway')
    
    # Get branch
    r = requests.get(f'{GITHUB_API}/repos/{user}/{repo_name}', headers=headers, timeout=15)
    branch = r.json().get('default_branch', 'main')
    
    # Upload files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files = {
        'app.py': 'Main Flask backend v2.1 (~1200 lines)',
        'requirements.txt': 'Python dependencies',
        'Procfile': 'Render startup config',
        'render.yaml': 'Render deployment config',
        '.gitignore': 'Ignore rules',
    }
    
    print(f'[5/5] Uploading {len(files)} files to GitHub...')
    for fname, desc in files.items():
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            print(f'  ⚠️  SKIP {fname} (not found)')
            continue
        
        with open(fpath, 'rb') as f:
            content_b64 = base64.b64encode(f.read()).decode()
        
        put_data = {
            'message': f'add {fname} - ChenYu AI v2.1 deploy',
            'content': content_b64,
            'branch': branch,
        }
        url = f'{GITHUB_API}/repos/{user}/{repo_name}/contents/{fname}'
        r = requests.put(url, headers=headers, json=put_data, timeout=30)
        
        status = '✅' if r.status_code in (200, 201) else f'❌({r.status_code})'
        print(f'  {status} {fname} - {desc}')
    
    repo_url = f'https://github.com/{user}/{repo_name}'
    print(f'\n{"=" * 55}')
    print(f'  🎉 CODE DEPLOYED TO GITHUB!')
    print(f'  Repo: {repo_url}')
    print(f'{"=" * 55}')
    return {'user': user, 'repo': repo_name, 'url': repo_url}


def main():
    print('\n╔══════════════════════════════════════════╗')
    print('║  🦞 ChenYu AI Auto Deploy Tool v2.0      ║')
    print('║     GitHub Cloud Deployment               ║')
    print('╚══════════════════════════════════════════╝\n')
    
    # Step 1: Get device code
    device_result = step1_request_device_code()
    if not device_result:
        return
    
    # Step 2: Wait for user auth on phone
    token = step2_wait_for_token(
        device_result['device_code'],
        device_result.get('interval', 5)
    )
    if not token:
        print('Failed to get token. Exiting.')
        return
    
    print(f'Token received: {token[:10]}...{token[-6:]}')
    
    # Step 3: Create repo and upload
    result = step3_create_repo_and_upload(token)
    
    if result:
        print(f'''
┌─────────────────────────────────────┐
│  🚀 NEXT STEP                       │
│                                     │  
│  Open this URL in browser:           │
│  https://dashboard.render.com       │
│                                     │  
│  Connect repo: {result['repo']}
│  Fill env vars (I can help!)        │
│  Deploy!                            │
└─────────────────────────────────────┘
''')


if __name__ == '__main__':
    main()
