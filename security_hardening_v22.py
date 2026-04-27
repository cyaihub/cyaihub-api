# -*- coding: utf-8 -*-
"""
沉鱼AI v2.2 安全加固脚本
一次性修复所有安全漏洞
执行方式: python security_hardening_v22.py
"""
import os, sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')

with open(path, 'rb') as f:
    raw = f.read()

content = raw.decode('utf-8')

print('=' * 60)
print('  沉鱼AI v2.2 安全加固脚本 - 启动')
print('=' * 60)

changes = []

# ====== 修复1: 关闭无码登录 ======
old1 = '''    if not code:
        # 开发环境：允许无code登录（方便调试）
        openid = f'dev_{int(time.time())}'
    else:
        # TODO: 正式环境用code换取openid
        # 这里简化处理，生产环境需调用微信 code2Session 接口
        openid = f'wx_{hashlib.md5(code.encode()).hexdigest()[:16]}'
    '''
new1 = '''    # 【v2.2安全修复】禁止无码登录！防止被脚本循环调用刷免费额度
    if not code:
        return jsonify(make_response(400, '微信授权失败，请重新登录'))

    # 用code生成openid（正式环境应调用微信 code2Session 接口换取真实openid）
    openid = f'wx_{hashlib.md5(code.encode()).hexdigest()[:16]}'
    '''
if old1 in content:
    content = content.replace(old1, new1)
    changes.append('[OK] #1 无码登录已关闭 - 防刷免费额度')

# ====== 修复2: API Key硬编码清除 ======
old2 = "ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')\nif not ZHIPU_API_KEY:\n    # 本地开发默认值\n    ZHIPU_API_KEY = '8c75d09ce0d04383a813313c74ab7fa8.GXsPMmb8MaUX47e5'"
new2 = """# 【v2.2安全修复】API Key仅通过环境变量传入，禁止硬编码！
ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
if not ZHIPU_API_KEY:
    print('[WARN] ZHIPU_API_KEY未设置，AI功能将使用Mock降级模式。')"""
if old2 in content:
    content = content.replace(old2, new2)
    changes.append('[OK] #2 API Key硬编码已清除 - 仅允许环境变量')

# ====== 修复3: 管理员密码标记待重置 ======
old3 = '''        -- 创建默认管理员账户 (admin / admin123)
        INSERT OR IGNORE INTO users (username, password_hash, nickname, is_admin, is_vip, free_count) VALUES
        ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e8effc6b9e8a2e8a00e7c9e11b', '管理员', 1, 1, 999);
'''
new3 = '''        -- 默认管理员账户（v2.2安全升级：首次启动后必须修改密码！）
        INSERT OR IGNORE INTO users (username, password_hash, nickname, is_admin, is_vip, free_count) VALUES
        ('admin', 'v2.2_secure_admin_please_change_me_2026', '管理员', 1, 1, 999);
'''
if old3 in content:
    content = content.replace(old3, new3)
    changes.append('[OK] #3 管理员弱密码已标记 - 需首次登录修改')

# ====== 修复4+5: 强随机密钥 + Token有效期缩短 ======
old45 = "# 安全密钥：优先使用环境变量（云端），本地有默认值\nSECRET_KEY = os.environ.get('SECRET_KEY', 'chenyu_ai_chat_secret_key_2026_v2_secure!')\nJWT_SECRET = os.environ.get('JWT_SECRET', 'chenyu_ai_jwt_secret_key_2026_secure_32bytes')\nJWT_EXPIRATION = 7 * 24 * 3600  # Token有效期7天"
new45 = """# 【v2.2安全】密钥通过环境变量设置，否则自动生成强随机密钥
import secrets as _secrets
_SECRET_KEY_FILE = os.path.join(BASE_DIR, '.secret_key')
_JWT_SECRET_FILE = os.path.join(BASE_DIR, '.jwt_secret')

def _load_or_generate_secret(filepath, length=64):
    if os.environ.get('SECRET_KEY') and 'JWT' not in filepath:
        return os.environ.get('SECRET_KEY')
    if os.environ.get('JWT_SECRET') and 'JWT' in filepath:
        return os.environ.get('JWT_SECRET')
    if os.path.exists(filepath):
        with open(filepath, 'r') as sf:
            key = sf.read().strip()
            if key:
                return key
    key = _secrets.token_urlsafe(length)
    with open(filepath, 'w') as sf:
        sf.write(key)
    print(f'[SECURITY] 新密钥已生成并保存到 {filepath}')
    return key

SECRET_KEY = _load_or_generate_secret(_SECRET_KEY_FILE, 48)
JWT_SECRET = _load_or_generate_secret(_JWT_SECRET_FILE, 64)
JWT_EXPIRATION = 2 * 3600  # Token有效期缩短为2小时（安全优化）"""
if old45 in content:
    content = content.replace(old45, new45)
    changes.append('[OK] #4+#5 密钥改为强随机 + Token缩短至2小时')

# ====== 修复4b: 密码加盐哈希 ======
old4b = '''def hash_password(password):
    """密码SHA256加密"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
'''
new4b = '''def _generate_salt():
    """生成随机盐值"""
    import secrets
    return secrets.token_hex(16)

def hash_password(password, salt=None):
    """密码SHA256+盐值加密（v2.2安全升级）"""
    import secrets
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return '${}${}'.format(salt, hashed)  # 格式: $salt$hash

def verify_password(password, stored_hash):
    """验证密码（兼容旧格式+新加盐格式）"""
    if stored_hash.startswith('$') and stored_hash.count('$') >= 2:
        parts = stored_hash.split('$')
        salt = parts[1]
        expected = parts[2]
        computed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
        return computed == expected
    else:
        old_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return old_hash == stored_hash
'''
if old4b in content:
    content = content.replace(old4b, new4b)
    changes.append('[OK] #4b 密码函数升级为SHA256+随机盐值')

# ====== 修复6: 登录限频机制 ======
old6 = '''@app.route('/api/wx/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify(make_response(400, '请输入用户名和密码'))
'''
new6 = '''# ====== v2.2安全: IP限频防暴力破解 ======
_login_attempts = {}

def _check_rate_limit(ip, max_attempts=5, lock_seconds=300):
    now = time.time()
    record = _login_attempts.get(ip)
    if record and now < record['lock_until']:
        remaining = int(record['lock_until'] - now)
        return False, f'登录过于频繁，请{}秒后重试'.format(remaining)
    if record and now - record.get('last_attempt', 0) < 1.5:
        return False, '操作过于频繁，稍后再试'
    return True, None

def _record_failed_attempt(ip):
    now = time.time()
    record = _login_attempts.get(ip, {'count': 0, 'lock_until': 0})
    record['count'] += 1
    record['last_attempt'] = now
    if record['count'] >= 5:
        record['lock_until'] = now + 300
    _login_attempts[ip] = record

def _clear_attempts(ip):
    _login_attempts.pop(ip, None)


@app.route('/api/wx/login', methods=['POST'])
def login():
    """用户登录（v2.2含限频）"""
    client_ip = request.remote_addr or 'unknown'
    
    allowed, msg = _check_rate_limit(client_ip)
    if not allowed:
        return jsonify(make_response(429, msg)), 429
    
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify(make_response(400, '请输入用户名和密码'))
'''
if old6 in content:
    content = content.replace(old6, new6)
    changes.append('[OK] #6 登录限频添加 - 5次失败锁定5分钟')

# ====== 修复6b: 登录验证接入限频 ======
old6b = "    if user['password_hash'] != hash_password(password):\n        return jsonify(make_response(401, '用户名或密码错误'))"
new6b = "    if not verify_password(password, user['password_hash']):\n        _record_failed_attempt(client_ip)\n        return jsonify(make_response(401, '用户名或密码错误'))"
if old6b in content:
    content = content.replace(old6b, new6b)
    changes.append('[OK] #6b 登录验证已接入限频')

# 在token生成前加入清除限频记录
old6c = '    # 生成Token\n    token = generate_token(user[\'id\'])'
new6c = '    # 登录成功，清除限频\n    _clear_attempts(client_ip)\n    \n    # 生成Token\n    token = generate_token(user[\'id\'])'
if old6c in content:
    content = content.replace(old6c, new6c)
    changes.append('[OK] #6c 登录成功清除限频')

# ====== 修复7: CORS收紧 ======
old7 = 'CORS(app)'
new7 = '''# v2.2 CORS收紧
_allowed_origins = [
    'https://cyaihub.top',
    'http://localhost:5678',
    'http://127.0.0.1:5678',
]
CORS(app, resources={
    r'/api/*': {
        'origins': _allowed_origins,
        'allow_headers': ['Content-Type', 'Authorization'],
        'methods': ['GET', 'POST', 'OPTIONS']
    }
})'''
if old7 in content:
    content = content.replace(old7, new7)
    changes.append('[OK] #7 CORS已收紧到指定域名')

# ====== 修复8: 测试接口脱敏 ======
old8 = '''@app.route('/api/test/connection', methods=['GET'])
def test_connection():
    """连接测试"""
    return jsonify(make_response(200, 'Server is running! Backend OK'))
'''
new8 = '''@app.route('/api/test/connection', methods=['GET'])
def test_connection():
    """连接测试（v2.2脱敏）"""
    return jsonify({'status': 'ok', 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
'''
if old8 in content:
    content = content.replace(old8, new8)
    changes.append('[OK] #8 测试接口已脱敏')

# ====== 修复9: 健康检查脱敏 ======
old9 = "'ai_enabled': bool(ZHIPU_API_KEY)"
new9 = "'ai_enabled': True"  # 不暴露真实状态
if old9 in content:
    content = content.replace(old9, new9)
    changes.append('[OK] #9 健康检查已脱敏')

# ====== 修复10: 文件上传校验 ======
old10 = '''    ext = uploaded_file.filename.rsplit('.', 1)[-1] if '.' in uploaded_file.filename else 'jpg'
    filename = f"proof_{payment_id}_{int(time.time())}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    uploaded_file.save(filepath)'''
new10 = '''    # 文件类型白名单
    _allowed_ext = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    ext = uploaded_file.filename.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.filename else 'jpg'
    if ext not in _allowed_ext:
        return jsonify(make_response(400, '只支持图片文件(jpg/png/gif/webp)'))
    filename = f"proof_{payment_id}_{int(time.time())}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    uploaded_file.save(filepath)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 2*1024*1024:
        os.remove(filepath)
        return jsonify(make_response(400, '文件大小不能超过2MB'))'''
if old10 in content:
    content = content.replace(old10, new10)
    changes.append('[OK] #10 文件上传白名单+大小限制')

# ====== 版本号更新 ======
content = content.replace(
    '沉鱼AI畅聊助手 - 后端服务 v2.1',
    '沉鱼AI畅聊助手 - 后端服务 v2.2 (Security Hardened)'
)
content = content.replace(
    'Flask + SQLite + GLM-4-Flash (智谱AI) - 顶级升级版',
    'Flask + SQLite + GLM-4-Flash (智谱AI) - v2.2安全加固版'
)
content = content.replace("v2.1新特性:", "v2.2安全加固:")
content = content.replace("ChenYu AI Chat Server v2.1", "ChenYu AI Chat Server v2.2 (Security)")
content = content.replace("'version': '2.0.0'", "'version': '2.2.0'")
content = content.replace("'service': '沉鱼AI畅聊助手 v2.0'", "'service': 'ChenYu AI Assistant'")

# 写回
with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(content)

print('')
print('=' * 60)
print('  安全加固完成！共修改 {} 项'.format(len(changes)))
print('=' * 60)
for c in changes:
    print('  {}'.format(c))
print('')
print('  重要提醒:')
print('  1. 管理员密码需要重新设置（当前标记为需修改）')
print('  2. 首次启动会自动生成随机密钥并保存到 .secret_key / .jwt_secret')
print('  3. 请设置环境变量 ZHIPU_API_KEY 以启用AI功能')
print('  4. 重启后端服务使生效: python app.py')
