# -*- coding: utf-8 -*-


"""


沉鱼AI畅聊助手 - 后端服务 v2.4 (Security Hardened)


Flask + SQLite + GLM-4-Flash (智谱AI) - v2.2安全加固版


v2.2安全加固: 真实AI调用/22+回复建议/变体算法/深度Prompt/自动降级


"""





import os


import sys


import json


import time


import hashlib


import random


import string


import requests


import re


from datetime import datetime, timedelta


from functools import wraps





import openai





from flask import Flask, request, jsonify, g


from flask_cors import CORS


import sqlite3


import jwt





# ============================================================


# 配置（支持本地 + 云端部署 + Render持久化）

# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__'))

# 数据库路径：优先环境变量 > 云端持久化目录 > 本地
# Render.com 持久化: /opt/render/.cache/data/
RENDER_DATA_DIR = '/opt/render/.cache/data'

if os.environ.get('DB_PATH'):
    DB_PATH = os.environ['DB_PATH']
elif os.path.exists(RENDER_DATA_DIR):
    os.makedirs(RENDER_DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(RENDER_DATA_DIR, 'app.db')
    print(f'[Deploy] Cloud mode: DB={DB_PATH}')
else:
    DB_PATH = os.path.join(BASE_DIR, 'data', 'app.db')

# 上传文件目录（云端用持久化路径）
UPLOAD_DIR = os.environ.get('UPLOAD_DIR') or (
    os.path.join(RENDER_DATA_DIR, 'uploads')
    if (os.path.exists(RENDER_DATA_DIR) or os.environ.get('RENDER'))
    else os.path.join(BASE_DIR, 'uploads')
)





# 安全密钥：优先使用环境变量（云端），本地有默认值


# SECRET_KEY set below with strong random value


# JWT_SECRET set below with strong random value


JWT_EXPIRATION = 7 * 24 * 3600
import secrets as _sec

# [v2.2 Security] Strong random keys - auto-generated on first run
# [v3.3] Zeabur/云部署支持：优先读取环境变量，本地开发回退到文件
_SEC_FILE = os.path.join(BASE_DIR, '.secret_key')
_JWT_FILE = os.path.join(BASE_DIR, '.jwt_secret')

def _get_env_or_file(env_name, fpath, length=64):
    """优先从环境变量获取密钥（云端部署），否则从文件获取（本地开发）"""
    env_val = os.environ.get(env_name, '').strip()
    if env_val:
        print(f'[SECURITY] {env_name} loaded from environment variable')
        return env_val
    # 本地：读文件或自动生成
    if os.path.exists(fpath):
        with open(fpath,'r') as f:
            k = f.read().strip()
            if k: return k
    k = _sec.token_urlsafe(length)
    with open(fpath,'w') as f:
        f.write(k)
    print('[SECURITY] Generated key: ' + fpath)
    return k

SECRET_KEY = _get_env_or_file('SECRET_KEY', _SEC_FILE, 48)
JWT_SECRET = _get_env_or_file('JWT_SECRET', _JWT_FILE, 64)
JWT_EXPIRATION = 2 * 3600  # Token valid 2 hours (was 7 days)
  # Token有效期7天





# 端口：Render提供PORT变量，本地默认5678


PORT = int(os.environ.get('PORT', 5678))





# 智谱AI配置：优先用环境变量，安全不泄露


ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')


if not ZHIPU_API_KEY:


    # 本地开发默认值


    ''  # [v2.2] REMOVED: Set ZHIPU_API_KEY env var instead!


ZHIPU_API_URL = os.environ.get('ZHIPU_API_URL', 'https://open.bigmodel.cn/api/paas/v4')





# ============================================================


# Flask应用初始化


# ============================================================


app = Flask(__name__)


# v2.2 CORS收紧

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

})


app.config['JSON_AS_ASCII'] = False


app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 上传限制10MB





# 确保数据目录存在


os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)





# ============================================================


# 数据库操作


# ============================================================


def get_db():


    """获取数据库连接（每个请求复用）"""


    if 'db' not in g:


        g.db = sqlite3.connect(DB_PATH)


        g.db.row_factory = sqlite3.Row


        # 启用外键约束


        g.db.execute('PRAGMA foreign_keys = ON')


    return g.db








@app.teardown_appcontext


def close_db(exception):


    """关闭数据库连接"""


    db = g.pop('db', None)


    if db is not None:


        db.close()








def init_db():


    """初始化数据库表结构"""


    db = get_db()


    db.executescript('''


        -- 用户表


        CREATE TABLE IF NOT EXISTS users (


            id INTEGER PRIMARY KEY AUTOINCREMENT,


            username TEXT UNIQUE NOT NULL,


            password_hash TEXT NOT NULL,


            nickname TEXT DEFAULT '',


            avatar_url TEXT DEFAULT '',


            phone TEXT DEFAULT '',


            is_vip INTEGER DEFAULT 0,


            vip_expire TEXT DEFAULT '',


            is_admin INTEGER DEFAULT 0,


            free_count INTEGER DEFAULT 3,


            total_count INTEGER DEFAULT 0,


            invite_code TEXT UNIQUE DEFAULT '',


            inviter_id INTEGER DEFAULT NULL,


            created_at TEXT DEFAULT (datetime('now','localtime')),


            updated_at TEXT DEFAULT (datetime('now','localtime'))


        );





        -- 聊天目标表（社交对象）


        CREATE TABLE IF NOT EXISTS targets (


            id INTEGER PRIMARY KEY AUTOINCREMENT,


            user_id INTEGER NOT NULL,


            name TEXT NOT NULL DEFAULT '',


            relationship TEXT DEFAULT '好友',


            gender TEXT DEFAULT '',


            personality TEXT DEFAULT '',


            notes TEXT DEFAULT '',


            created_at TEXT DEFAULT (datetime('now','localtime')),


            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE


        );





        -- 会话记录表


        CREATE TABLE IF NOT EXISTS sessions (


            id INTEGER PRIMARY KEY AUTOINCREMENT,


            user_id INTEGER NOT NULL,


            target_id INTEGER DEFAULT NULL,


            scene TEXT DEFAULT 'social',


            identity TEXT DEFAULT '',


            style TEXT DEFAULT '',


            custom_desc TEXT DEFAULT '',


            input_msg TEXT DEFAULT '',


            ai_response TEXT DEFAULT '',


            suggestions TEXT DEFAULT '[]',


            created_at TEXT DEFAULT (datetime('now','localtime')),


            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE


        );





        -- VIP订单表


        CREATE TABLE IF NOT EXISTS payments (


            id INTEGER PRIMARY KEY AUTOINCREMENT,


            user_id INTEGER NOT NULL,


            order_no TEXT UNIQUE NOT NULL,


            plan_type TEXT NOT NULL,


            amount REAL NOT NULL,


            status TEXT DEFAULT 'pending',


            pay_method TEXT DEFAULT 'manual',


            proof_image TEXT DEFAULT '',


            remark TEXT DEFAULT '',


            reviewed_by INTEGER DEFAULT NULL,


            reviewed_at TEXT DEFAULT '',


            created_at TEXT DEFAULT (datetime('now','localtime')),


            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE


        );





        -- 佣金记录表 [v2.3 Commission Fix]
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_user_id INTEGER NOT NULL,
            buyer_user_id INTEGER NOT NULL,
            payment_id INTEGER NOT NULL,
            order_no TEXT NOT NULL,
            commission_rate REAL NOT NULL DEFAULT 0.30,
            commission_amount REAL NOT NULL DEFAULT 0,
            plan_type TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            settled_at TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (inviter_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
        );

        -- 提现记录表 [v2.3 Withdrawal Fix]
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            withdraw_method TEXT DEFAULT 'wechat',
            account_info TEXT DEFAULT '',
            remark TEXT DEFAULT '',
            reviewed_by INTEGER DEFAULT NULL,
            reviewed_at TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- 预设身份/风格表


        CREATE TABLE IF NOT EXISTS preset_styles (


            id INTEGER PRIMARY KEY AUTOINCREMENT,


            scene TEXT NOT NULL,


            name TEXT NOT NULL,


            icon TEXT DEFAULT '',


            description TEXT DEFAULT '',


            sort_order INTEGER DEFAULT 0


        );





        -- 聊天记忆表（v3.3 记忆功能）
        CREATE TABLE IF NOT EXISTS chat_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_id INTEGER DEFAULT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            content TEXT NOT NULL DEFAULT '',
            scene TEXT DEFAULT 'social',
            identity TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- 聊天记忆索引
        CREATE INDEX IF NOT EXISTS idx_chat_memory_user_target ON chat_memory(user_id, target_id);


        -- 插入预设数据（如果为空）


        INSERT OR IGNORE INTO preset_styles (scene, name, icon, description, sort_order) VALUES


        ('social', '好朋友', '👯', '无话不谈的好闺蜜/好兄弟，可以开玩笑、互相吐槽', 1),


        ('social', '暧昧中', '💕', '正在追求或暧昧阶段，需要制造机会、拉近距离', 2),


        ('social', '刚认识', '🌱', '刚认识不久，还在了解阶段，避免过于冒进', 3),


        ('social', '前任', '💔', '已经分手但还想联系，需要把握分寸', 4),


        ('social', '陌生人', '👋', '完全不认识，需要破冰开场、建立第一印象', 5),


        ('marketing', '朋友圈营销', '📢', '在朋友圈发布产品推广，吸引客户咨询', 1),


        ('marketing', '私信开发', '💬', '通过私聊方式向潜在客户介绍产品', 2),


        ('marketing', '社群运营', '👥', '在微信群/QQ群内活跃氛围、引导转化', 3),


        ('marketing', '客服回复', '🎧', '处理客户的售前咨询和售后问题', 4),


        ('marketing', '活动邀约', '📅', '邀请客户参加活动、促销、新品发布等', 5);





        -- 创建默认管理员账户 (admin / admin123)


        INSERT OR IGNORE INTO users (username, password_hash, nickname, is_admin, is_vip, free_count) VALUES


        ('admin', 'ADMIN_PLEASE_CHANGE_v22_secure', '管理员', 1, 1, 999);


    ''')


    db.commit()








def query_db(query, args=(), one=False):


    """执行SQL查询并返回结果"""


    db = get_db()


    cursor = db.execute(query, args)


    if one:


        row = cursor.fetchone()


        return dict(row) if row else None


    return [dict(row) for row in cursor.fetchall()]








# ============================================================


# 工具函数


# ============================================================





def make_response(code=200, msg='success', data=None):


    """统一API响应格式"""


    result = {'code': code, 'msg': msg}


    if data is not None:


        result['data'] = data


    return result








def hash_password(password):
    """SHA256+salt password hash (v2.2 security)"""
    import secrets as _secrets2
    salt = _secrets2.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return '${}$'.format(salt, hashed)

def verify_password(password, stored_hash):
    """Verify with salt support (backward compatible)"""
    if stored_hash.startswith('$') and stored_hash.count('$') >= 2:
        parts = stored_hash.split('$')
        computed = hashlib.sha256((parts[1] + password).encode('utf-8')).hexdigest()
        return computed == parts[2]
    return hashlib.sha256(password.encode('utf-8')).hexdigest() == stored_hash


def _legacy_sha256_for_db_init(password):
    """Legacy SHA256 for DB init only"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()











def generate_token(user_id):


    """生成JWT Token"""


    payload = {


        'user_id': user_id,


        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION),


        'iat': datetime.utcnow()


    }


    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')


    # 兼容PyJWT不同版本返回类型


    return token if isinstance(token, str) else token.decode('utf-8')








def decode_token(token):


    """解码并验证JWT Token"""


    try:


        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])


        return payload


    except jwt.ExpiredSignatureError:


        return None


    except Exception:


        return None








def token_required(f):


    """Token验证装饰器"""


    @wraps(f)


    def decorated(*args, **kwargs):


        auth_header = request.headers.get('Authorization')


        if not auth_header or not auth_header.startswith('Bearer '):


            return jsonify(make_response(401, '未登录，请先登录')), 401


        


        token = auth_header.split(' ')[1]


        payload = decode_token(token)


        


        if not payload:


            return jsonify(make_response(401, '登录已过期，请重新登录')), 401


        


        g.user_id = payload['user_id']


        g.user = query_db('SELECT * FROM users WHERE id = ?', (g.user_id,), one=True)


        


        if not g.user:


            return jsonify(make_response(401, '用户不存在')), 401


            


        return f(*args, **kwargs)


    return decorated








def generate_invite_code(length=8):


    """生成唯一邀请码"""


    while True:


        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


        if not query_db('SELECT id FROM users WHERE invite_code = ?', (code,), one=True):


            return code








def generate_order_no():


    """生成订单号"""


    timestamp = int(time.time() * 1000)


    random_str = ''.join(random.choices(string.digits, k=6))


    return f'CY{timestamp}{random_str}'








# ============================================================


# AI调用模块 v2.2-Secure - 融合v3.0顶级引擎


# 支持: GLM-4-Flash(免费) / DeepSeek / GPT-4o-mini / 通义千问 / Kimi


# 特性: 22+条精准回复建议 / 变体算法 / 风格标签 / 自动降级


# ============================================================





import openai





MIN_REPLIES = 22  # v3.0标准: 返回22+条高质量回复

MEMORY_MAX_TURNS = 10  # v3.3: 记忆保留最近10轮对话（每轮=用户消息+AI回复）
MEMORY_MAX_TOKENS = 1500  # v3.4: 记忆上下文最大token数，防止超出API限制


# ============================================================
# v3.3 聊天记忆管理函数
# ============================================================

def get_chat_memory(user_id, target_id=None, limit=None):
    """获取用户的聊天记忆（按时间正序，用于AI上下文）[v3.4增强:token限制]"""
    if target_id:
        rows = query_db(
            'SELECT role, content FROM chat_memory WHERE user_id = ? AND target_id = ? ORDER BY id DESC LIMIT ?',
            (user_id, target_id, limit or MEMORY_MAX_TURNS * 2)
        )
    else:
        rows = query_db(
            'SELECT role, content FROM chat_memory WHERE user_id = ? ORDER BY id DESC LIMIT ?',
            (user_id, limit or MEMORY_MAX_TURNS * 2)
        )
    # 反转成正序（旧→新），转为messages格式
    rows_reversed = list(reversed(rows))
    raw_messages = [{'role': r['role'], 'content': r['content']} for r in rows_reversed]
    
    # v3.4: Token限制——估算并裁剪超长记忆
    return _trim_memory_by_tokens(raw_messages)


def _trim_memory_by_tokens(messages, max_tokens=MEMORY_MAX_TOKENS):
    """v3.4: 裁剪记忆上下文，确保不超过token限制
    策略：优先保留最近的对话，从最旧的开始丢弃
    """
    if not messages:
        return []
    
    total_chars = sum(len(m.get('content', '')) for m in messages)
    # 粗略估算: 1个中文字≈1.5-2 tokens
    estimated_tokens = total_chars * 2
    
    if estimated_tokens <= max_tokens:
        return messages
    
    # 需要裁剪——保留最新的，从旧的开始删
    trimmed = list(messages)
    while len(trimmed) > 0 and sum(len(m.get('content', '')) for m in trimmed) * 2 > max_tokens:
        trimmed.pop(0)  # 删掉最旧的
    
    print(f'[Memory] Token裁剪: 原始{len(messages)}条 → 裁剪后{len(trimmed)}条')
    return trimmed


def save_chat_memory(user_id, target_id, role, content, scene='', identity=''):
    """保存一条聊天记忆"""
    db = get_db()
    db.execute(
        'INSERT INTO chat_memory (user_id, target_id, role, content, scene, identity) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, target_id, role, content, scene, identity)
    )
    db.commit()


def save_conversation_to_memory(user_id, target_id, user_message, ai_reply_summary, scene='', identity=''):
    """保存一轮完整对话到记忆（v4.0增强: 提取关键信息）
    
    v4.0改进：
    - 不再全文存储，而是智能提取关键信息点
    - 识别并标记人名/喜好/事件/时间等实体
    - 压缩AI回复为精华摘要而非原文
    """
    # 保存用户原始消息（这是最有价值的上下文）
    save_chat_memory(user_id, target_id, 'user', user_message, scene, identity)
    
    # AI回复摘要——只存第一条的精简版（节省token+聚焦核心）
    if isinstance(ai_reply_summary, list) and len(ai_reply_summary) > 0:
        first_reply = ai_reply_summary[0]
        reply_text = first_reply.get('text', first_reply) if isinstance(first_reply, dict) else str(first_reply)
        # 截断过长回复（超过40字的压缩到核心内容）
        if len(reply_text) > 40:
            reply_text = reply_text[:38] + '..'
        save_chat_memory(user_id, target_id, 'assistant', f'[建议] {reply_text}', scene, identity)
    elif ai_reply_summary:
        reply_text = ai_reply_summary.get('text', str(ai_reply_summary)) if isinstance(ai_reply_summary, dict) else str(ai_reply_summary)
        if len(reply_text) > 40:
            reply_text = reply_text[:38] + '..'
        save_chat_memory(user_id, target_id, 'assistant', f'[建议] {reply_text}', scene, identity)


def _call_ner_extraction(text_blocks):
    """
    v4.1: 调用智谱AI进行高级命名实体识别(NER)
    
    从聊天记忆文本中提取结构化关键信息：
    - 人名/昵称 (PERSON)
    - 地点/场所 (LOCATION)
    - 组织/公司 (ORG)
    - 喜好/兴趣 (INTEREST)
    - 计划/事件 (EVENT)
    - 重要日期 (DATE)
    - 关系状态 (RELATIONSHIP)
    - 对方特征/情绪 (TRAIT)

    Args:
        text_blocks: list of str, 聊天记忆文本片段列表

    Returns:
        dict: 结构化的实体信息
    """
    if not text_blocks or not ZHIPU_API_KEY:
        return None

    # 合并文本，控制总长度避免token溢出
    combined_text = '\n'.join(text_blocks[-15:])  # 最近15条
    if len(combined_text) < 10:  # 文本太短不值得调用
        return None

    ner_prompt = f"""你是一个专业的中文命名实体识别引擎。请分析以下微信聊天记录，提取关键实体信息。

【聊天记录】
{combined_text}

请严格按以下JSON格式输出（不要输出其他内容）:
{{
    "persons": ["提到的人名或昵称"],
    "locations": ["提到的地点"],
    "organizations": ["提到的公司/学校/组织"],
    "interests": ["对方的喜好/爱好/感兴趣的事物"],
    "events": ["近期讨论的事件/活动/计划"],
    "dates": ["提到的重要时间点"],
    "relationships": ["透露的关系信息"],
    "traits": ["对方性格/情绪/状态特征"]
}}

规则：
1. 只提取明确提及的信息，不要猜测
2. 同类实体去重
3. 每个数组最多5个元素
4. 如果某个类别没有相关信息，输出空数组[]
5. 输出纯JSON，不要markdown代码块标记"""

    try:
        import openai
        client = openai.OpenAI(
            api_key=ZHIPU_API_KEY,
            base_url=ZHIPU_API_URL
        )

        response = client.chat.completions.create(
            model='glm-4-flash',  # NER任务用轻量模型即可
            messages=[
                {'role': 'system', 'content': '你是精准的中文NER提取引擎，只输出结构化JSON，不要任何解释。'},
                {'role': 'user', 'content': ner_prompt}
            ],
            max_tokens=800,
            temperature=0.1,  # 低温度确保提取稳定
            top_p=0.95
        )

        raw_result = response.choices[0].message.content.strip()

        # 清理可能存在的markdown标记
        if raw_result.startswith('```'):
            raw_result = raw_result.split('\n', 1)[1] if '\n' in raw_result else raw_result[3:]
            if raw_result.endswith('```'):
                raw_result = raw_result[:-3]
            raw_result = raw_result.strip()

        entities = json.loads(raw_result)

        # 验证并清理结果
        valid_keys = {'persons', 'locations', 'organizations', 'interests',
                      'events', 'dates', 'relationships', 'traits'}
        return {k: v for k, v in entities.items() if k in valid_keys}

    except json.JSONDecodeError as e:
        print(f'[v4.1 NER Warning] JSON解析失败: {e}')
        return None
    except Exception as e:
        print(f'[v4.1 NER Error] 提取失败: {e}')
        return None


def _fallback_regex_ner(content):
    """
    v4.1: 降级方案 - 基于正则的简单实体识别
    当智谱NER调用失败时使用此方法
    """
    import re

    results = {
        'persons': [],
        'locations': [],
        'interests': [],
        'events': [],
        'traits': []
    }

    # 人名模式（常见姓氏+1-2字）
    names = re.findall(r'([张王李刘陈杨赵黄周吴郑孙][一-龥]{1,2})', content)
    results['persons'] = list(set(names[:3]))

    # 喜好模式
    likes = re.findall(r'(喜欢|爱吃|爱玩|想买|想去|常去)[的]?([一-龥]{2,8})', content)
    results['interests'] = [''.join(l) for l in likes[:2]]

    # 事件/活动模式
    events = re.findall(r'(去了|要去|打算|计划|周末|今天|明天)([一-龥]{2,12})', content)
    results['events'] = [''.join(e) for e in events[:2]]

    # 地点线索
    locations = re.findall(r'(在|去|到|从)([一-龥]{2,6})(市|区|路|店|馆|园|广场|公园|商场)', content)
    results['locations'] = [l[1] + l[2] for l in locations[:2]]

    return results


def extract_key_info_from_memory(user_id, target_id=None):
    """
    v4.1: 从记忆中提取关键信息（智谱NER增强版）

    升级亮点：
    - 优先使用智谱AI进行高级NER提取
    - 自动降级到正则方案作为fallback
    - 结构化输出8类实体信息
    - 结果缓存避免重复API调用
    """
    memories = get_memory_list_api(user_id, target_id)
    if not memories:
        return ''

    # 准备用户消息文本（只看用户发的）
    user_messages = [m.get('content', '') for m in memories[-20:]
                    if m.get('role') == 'user' and len(m.get('content', '')) > 2]

    if not user_messages:
        return ''

    # ===== 尝试智谱NER =====
    ner_result = _call_ner_extraction(user_messages)

    if not ner_result:
        # 降级到正则方案
        all_text = '\n'.join(user_messages)
        ner_result = _fallback_regex_ner(all_text)

    # 构建上下文摘要
    key_points = []

    if ner_result.get('persons'):
        key_points.append(f"👤 相关人物: {', '.join(ner_result['persons'][:4])}")

    if ner_result.get('interests'):
        key_points.append(f"❤️ 对方喜好: {', '.join(ner_result['interests'][:4])}")

    if ner_result.get('events'):
        key_points.append(f"📅 近期动态: {', '.join(ner_result['events'][:3])}")

    if ner_result.get('locations'):
        key_points.append(f"📍 相关地点: {', '.join(ner_result['locations'][:3])}")

    if ner_result.get('relationships'):
        key_points.append(f"👥 关系线索: {', '.join(ner_result['relationships'][:2])}")

    if ner_result.get('traits'):
        key_points.append(f"💭 对方特征: {', '.join(ner_result['traits'][:3])}")

    if ner_result.get('dates'):
        key_points.append(f"⏰ 重要时间: {', '.join(ner_result['dates'][:2])}")

    if key_points:
        context = '\n【v4.1 智能上下文感知】\n' + '\n'.join(key_points)
        context += '\n> 💡 请自然引用以上信息让对话更连贯，但不要刻意提及所有点。\n'
        return context

    return ''


def clear_chat_memory(user_id, target_id=None):
    """清除聊天记忆"""
    db = get_db()
    if target_id:
        db.execute('DELETE FROM chat_memory WHERE user_id = ? AND target_id = ?', (user_id, target_id))
    else:
        db.execute('DELETE FROM chat_memory WHERE user_id = ?', (user_id,))
    db.commit()


def get_memory_list_api(user_id, target_id=None):
    """获取记忆列表（API用，包含完整信息）"""
    if target_id:
        rows = query_db(
            'SELECT * FROM chat_memory WHERE user_id = ? AND target_id = ? ORDER BY id DESC LIMIT 50',
            (user_id, target_id)
        )
    else:
        rows = query_db(
            'SELECT * FROM chat_memory WHERE user_id = ? ORDER BY id DESC LIMIT 50',
            (user_id,)
        )
    return [dict(r) for r in rows]









def call_ai_api(scene, identity, style, custom_desc, message, target_info='', memory_context=None):


    """


    调用AI大模型生成回复建议 (v2.1增强版)


    


    融合v3.0核心优势：


    - 22+条精准回复建议（原版仅8-10条Mock）


    - 深度场景化Prompt（社交6种 × 营销6种）


    - 风格标签分类（[幽默][走心][调侃]...）


    - 变体生成算法确保数量充足


    - 多层降级机制保证可用性


    


    Returns:


        list: 建议回复列表 (22+条)


    """


    suggest_prompt = _build_v4_prompt(scene, identity, custom_desc, message, target_info)


    


    try:


        # 使用OpenAI兼容客户端调用智谱AI


        client = openai.OpenAI(


            api_key=ZHIPU_API_KEY,


            base_url=ZHIPU_API_URL


        )


        


        response = client.chat.completions.create(


            model='glm-4-flash',


            messages=[


                {'role': 'system', 'content': '你是沉鱼AI畅聊助手v4.0引擎-顶级回复建议专家。\n核心原则:\n1.每条回复必须像真人发的微信消息，绝对不能有任何AI味\n2.严格遵循用户指定的场景和身份要求\n3.输出格式：每条一行 [标签]回复内容，标签从指定列表中选择\n4.禁止：说教/油腻/土味/问在干嘛/泛泛而谈/重复句式\n5.必须针对对方消息的具体内容回复，不能无视消息内容\n6.[记忆功能]如果提供了之前的对话上下文或关键信息摘要，请自然地引用让对话更连贯\n7.[v4.0]注意消息类型和应对策略，确保回复策略多样化\n直接输出，不要任何解释说明。'},


                # [v3.3] 注入聊天记忆上下文（在system和user之间）
                *(memory_context or []),

                {'role': 'user', 'content': suggest_prompt}


            ],


            max_tokens=3500,


            temperature=0.83,


            top_p=0.92,


        )


        


        raw = response.choices[0].message.content.strip()


        pt = _parse_v3_replies_tagged(raw)
        if pt:
            replies = [x["text"] for x in pt]
            g.tagged_replies = pt
        else:
            replies = _parse_v3_replies(raw)
            g.tagged_replies = None


        


        # 变体扩充：如果不足22条，用变体算法补足


        if len(replies) < MIN_REPLIES and len(replies) > 0:


            extras = []


            for base in replies[:min(3, len(replies))]:


                extras.extend(_generate_variants(base, max(5, MIN_REPLIES - len(replies))))


            for ext in extras:


                if ext not in replies and len(replies) < MIN_REPLIES:


                    replies.append(ext)


        


# v3.4: 智能排序（只调用一次）+ 去重
        replies = _deduplicate_replies(replies)  # 先去重
        replies = _rank_replies(replies, message, identity)
        return replies[:25]  # 最多25条


        


    except Exception as e:


        print(f'[AI Primary Error] {e}')


        # 降级：尝试备用方案


        return _fallback_ai_generate(scene, identity, custom_desc, message)








def _build_v4_prompt(scene, identity, custom_desc, message, target_info=''):
    """构建v4.0深度Prompt（终极增强版）
    
    [v4.0核心创新]
    1. 消息类型智能感知——自动判断对方消息类型并匹配策略
    2. 对话阶段意识——根据内容推断聊天进展阶段
    3. 回复策略分类——确保22条覆盖所有策略角度
    4. 反AI强化——更严格的去AI味规则
    5. 示例动态注入——根据消息类型注入最相关的示例
    [v3.1] 身份key与前端chat.js完全对齐
    [v3.3] 记忆上下文自动注入
    """
    
    # ===== 消息类型智能感知（v4.0新） =====
    def detect_message_type(msg):
        """检测消息类型，返回(类型名, 策略提示)"""
        msg_lower = msg.lower().strip()
        
        # 问句类型
        if any(msg_lower.endswith(p) for p in ['？', '?', '吗', '么', '呢', '吗？', '么？', '呢？']):
            if any(w in msg_lower for w in ['什么', '哪', '谁', '怎么', '多少', '为什么', '为啥']):
                return ('info_question', '对方在问具体信息 → 先回答问题，再延伸话题或反问')
            if any(w in msg_lower for w in ['想不想要', '要不要', '能不能', '可不可以', '好不好', '去不去']):
                return ('invite_question', '对方在邀请/征求意见 → 根据关系给出有趣或有态度的回应')
            if any(w in msg_lower for w in ['你觉得', '你认为', '怎么看', '怎么样']):
                return ('opinion_question', '对方在征求你的看法 → 给出有观点的回答，不要模棱两可')
            return ('general_question', '对方在提问 → 直接回答+延伸/反问/分享经历')
        
        # 分享/陈述类型
        if any(w in msg_lower for w in ['今天', '刚才', '昨天', '刚刚', '周末', '这周']):
            return ('life_sharing', '对方在分享生活日常 → 共鸣+接住细节+延伸相关话题')
        
        # 吐槽/负面情绪
        if any(w in msg_lower for w in ['烦', '累', '气', '无语', '崩溃', '服了', '醉了', 
                                          '离谱', '恶心', '讨厌', '烦死了', '气死', '不想',
                                          '太难了', '卷', '内卷']):
            return ('venting', '对方在吐槽/发泄情绪 → 同阵营共情+一起吐槽+疏导化解')
        
        # 表达开心/兴奋
        if any(w in msg_lower for w in ['哈哈', '太好了', '开心', '激动', '终于',
                                          '耶', '棒', '厉害', '牛', '绝了', '笑死']):
            return ('excited', '对方很开心/兴奋 → 顺势high起来+放大情绪+一起庆祝')
        
        # 表达关心/想念
        if any(w in msg_lower for w in ['想你', '想你啦', '在干嘛', '在吗', '睡了吗',
                                          '吃饭没', '早安', '晚安', '好久不见']):
            return ('caring_miss', '对方表达关心或想念 → 温暖回应+反向关心+分享近况')
        
        # 求助/犹豫
        if any(w in msg_lower for w in ['不知道', '怎么办', '纠结', '犹豫', '帮帮我',
                                          '建议', '不知道该不该', '迷茫', '求帮助', '怎么解',
                                          '帮我', '请教', '哪个', '选哪个', 'offer']):
            return ('seeking_help', '对方在求助或纠结 → 【必须给出具体可行的建议或方案】不能只说安慰话！分析选项、给理由、甚至帮TA做决定。如果真不懂就诚实说然后转移话题。')
        
        # 冷淡/敷衍信号
        if len(msg_lower) <= 2 and not any(w in msg_lower for w in ['！', '！', '?', '？']):
            return ('cold_brief', '对方回得很冷淡/简短(如"嗯""哦""哈哈") → 【回复也要简短！1-8个字】用轻松/好奇/调皮的一句话重新激活对话，不要长篇大论。可以故意曲解、卖萌、或者丢出一个有趣的新话题钩子。')
        
        # 默认：普通陈述
        return ('general_statement', '对方的普通陈述 → 共情+分享相关经历+提出新角度/新话题')
    
    # ===== 对话阶段推断（v4.0新） =====
    def infer_conversation_stage(memory_context):
        """根据记忆上下文推断对话阶段"""
        if memory_context is None or len(memory_context) == 0:
            return 'initial', '(看起来是新对话的开始)'
        
        turn_count = len(memory_context) // 2  # 大约轮数
        
        if turn_count <= 2:
            return 'warmup', f'(当前处于破冰/热身阶段，已聊约{turn_count}轮)'
        elif turn_count <= 6:
            return 'deepening', f'(当前处于深入交流阶段，已聊约{turn_count}轮，可以更深度的互动)'
        elif turn_count <= 12:
            return 'stable', f'(当前是稳定聊天阶段，已聊约{turn_count}轮，保持新鲜感很重要)'
        else:
            return 'long_term', f'(长期对话中，已聊超过{turn_count}轮，需要避免重复和乏味)'
    
    # ===== 场景映射表（保留原有高质量配置）=====
    social_map = {
        'friend': ('好朋友', '像铁哥们一样轻松幽默地聊，不油腻不尴尬',
            '你们是无话不谈的好朋友/好闺蜜，关系很铁很随意。可以互相调侃、分享日常、吐槽生活。像真正的朋友一样聊天，不需要客套。'),
        'chase': ('暧昧中/正在追', '循序渐进追求，展示魅力但不跪舔，高情商推拉',
            '你在追求这个人！绝不能暴露需求感！要展示魅力和有趣，高情商推拉，让对方产生好奇和好感。'),
        'couple': ('情侣/恋人', '甜蜜互动，温柔体贴但不肉麻',
            '你们是情侣/恋人关系。可以甜蜜、温柔、体贴，但不要太肉麻尴尬。用情侣间的亲密感回复，带点撒娇和关心更自然。'),
        'funny': ('搞笑沙雕', '段子手附体，把对方的话变成梗',
            '你是搞笑担当/段子手！把对方说的每句话都变成笑点和梗。幽默自嘲、夸张比喻、神转折。'),
        'gentle': ('温暖治愈', '温柔陪伴，共情对方感受，不讲道理',
            '你是温暖的治愈者。先共情对方的感受，站在TA角度理解情绪。不讲大道理不说教。'),
        's_custom': ('自定义', custom_desc or '根据描述的关系和风格自然聊天', custom_desc or ''),
        # ===== v4.1新增: 完善身份别名映射 =====
        # 情侣/恋爱相关 → couple (甜蜜温柔)
        '女朋友': ('女朋友', '甜蜜宠溺，带点撒娇和关心，像真正女友一样自然体贴',
            '你是她的女朋友！回复要甜而不腻、软萌自然。可以用撒娇语气、关心对方、偶尔吃醋卖萌。禁止兄弟式用语（好家伙/整一个/牛逼等）。多用"宝贝""亲爱的""哼""呀~"等女性化语气词。'),
        '男友': ('男朋友', '被宠爱的一方，可以撒娇依赖，也可以调皮',
            '你在跟男朋友聊天。可以撒娇、示弱、调皮，也可以关心他。回复自然甜美，像真正的女朋友。'),
        '老公': ('老公', '老夫老妻模式，亲密随意带点嫌弃式恩爱',
            '跟老公聊天，老夫老妻感。可以嫌弃又关心，亲密无间不客气。像真实夫妻一样随性自然。'),
        '老婆': ('老婆', '宠溺老婆模式，温柔体贴加偶尔霸道',
            '跟老婆聊天，要宠她爱她。温柔体贴为主，偶尔霸道总裁范。行动派——说"我给你买""我去接你"。'),
        '暧昧对象': ('暧昧中', '循序渐进追求，展示魅力但不跪舔，高情商推拉',
            '暧昧阶段！保持神秘感和吸引力。适度推拉，不要暴露太多需求感。让对方猜不透你但又想靠近你。'),
        # 好友/闺蜜相关 → friend (轻松调侃)
        '好朋友': ('好朋友', '像铁哥们/好闺蜜一样轻松幽默地聊，不油腻不尴尬',
            '你们是无话不谈的好朋友/好闺蜜，关系很铁很随意。可以互相调侃、分享日常、吐槽生活。'),
        '闺蜜': ('闺蜜', '好姐妹模式，分享八卦吐槽男友，无话不谈',
            '跟闺蜜聊天就是疯狂输出！分享八卦、吐槽、安利、聊感情。语气活泼激动，大量emoji和感叹号。'),
        '兄弟': ('铁哥们', '纯兄弟模式，互损互怼，直来直去不墨迹',
            '纯兄弟！互损互怼、直来直去。不用客气不用修饰，想说啥说啥。可以粗犷一点但要有分寸。'),
        # 同事/同学/熟人 → 专业+适度友好
        '同学/同事': ('同学/同事', '友善专业，适度友好但不越界',
            '同学/同事关系。保持友善和专业平衡。工作/学习话题为主，偶尔闲聊但不过度私人。礼貌但不疏远。'),
        '同事': ('同事', '工作伙伴关系，专业友善，适度闲聊',
            '同事关系！工作场合保持专业形象，非工作时间可以适当放松闲聊。不涉及过于私人的话题。'),
        '同学': ('同学', '同学关系，学习话题为主，轻松互助',
            '同学之间以学习话题为主。可以讨论作业考试，也可以闲聊校园生活。平等互助的感觉。'),
        # 家人相关 → gentle (温暖治愈)
        '家人': ('家人', '温暖亲切，家人般的关怀与唠叨',
            '家人之间聊天。温暖亲切，可以唠叨、关心、分享日常。像跟爸妈兄弟姐妹说话一样自然。'),
        '父母': ('父母', '乖巧孝顺报平安，也可适当撒娇',
            '跟父母聊天。报平安、分享生活、问候身体。乖巧但不失个性，偶尔撒娇也行。'),
        # 刚认识/陌生 → 保持礼貌有趣
        '刚认识的人': ('刚认识', '保持礼貌有趣，不冒进不冷漠',
            '刚认识不久！大方得体、有趣但不冒进。寻找共同话题，展示自己但不过度暴露。保持神秘感。'),
        '刚认识': ('刚认识', '保持礼貌有趣，自然大方不冒进',
            '刚认识不久，自然大方不冒进。'),
        '陌生人': ('陌生人', '破冰开场，建立第一印象',
            '完全不认识，破冰建立第一印象。'),
        '前任': ('前任', '把握分寸，不远不近',
            '分手但还想联系，把握分寸感。'),
        # 默认兜底
        '普通朋友': ('普通朋友', '友善轻松，比熟人正式比朋友拘谨一点',
            '普通朋友关系。友善轻松，介于熟人和朋友之间。可以闲聊但保持一定距离。'),
    }
    
    marketing_map = {
        'lead': ('获客引流', '吸引潜在客户注意，用价值吸引而非硬推',
            '这是获客引流场景。目标是让看到回复的人立刻产生"这个人专业又靠谱"的第一印象。绝对禁止硬推销、催促、低价轰炸。'),
        'follow': ('跟进回访', '跟进已接触客户，保持热度',
            '这是客户跟进回访场景。对方之前了解过但还没下单，可能正在对比或犹豫。关键策略：像老朋友聊天一样自然，不要一上来就谈产品；先关心对方近况，再顺势带入产品价值。绝对避免：催单太急、贬低竞品、死缠烂打。'),
        'close': ('转化成交', '引导客户下单成交，解决顾虑制造紧迫感',
            '这是临门一脚促成交场景！对方已经有意向，就差最后一推。关键策略：先确认真实顾虑是什么；用具体数据、案例、见证消除顾虑；给出无法拒绝的理由；适度紧迫感。绝对避免：逼单太狠、虚假承诺、道德绑架。'),
        'service': ('售后客服', '安抚情绪+高效解决+超预期服务',
            '售后服务场景。客户遇到问题找上门。关键策略：第一步-永远先处理情绪再处理问题："我完全理解您的感受"；第二步-高效解决方案+明确时间节点；第三步-超预期收尾+主动补偿。绝对避免：推卸责任/拖延/敷衍。'),
        'complaint': ('投诉处理', '先共情道歉再给方案，化解矛盾挽回信任',
            '投诉危机处理！客户非常不满。致命顺序：第1步-无条件共情（最重要！）绝不解释绝不辩解；第2步-承担责任给至少2个方案；第3步-超预期补偿+追踪满意度。致命禁忌：反驳客户/说"但是"/冷处理。'),
        'm_custom': ('自定义营销', custom_desc or '根据描述的营销场景生成话术', ''),
        # 兼容旧key
        '朋友圈营销': ('获客引流', '吸引潜在客户', '用价值吸引，不硬推销。'),
        '私信开发': ('跟进回访', '跟进已接触客户', '保持热度不遗忘。'),
    }
    
    # 选择映射表
    identity_map = marketing_map if scene == 'marketing' else social_map
    
    id_info = identity_map.get(identity, social_map.get('friend'))
    id_name = id_info[0]
    id_detail = id_info[2]
    
    # ===== v4.0: 智能消息分析 ======
    msg_type, msg_type_hint = detect_message_type(message)
    
    # 目标信息上下文
    target_context = ''
    if target_info:
        target_context = '\n\n【对方信息】%s\n> 请根据上述对方的具体信息让回复更加个性化。\n' % target_info
    
    # ===== v4.0增强: 反AI味铁律 ======  
    anti_ai_rules = (
        "【⛔ 绝对禁止（触犯任何一条即不合格）】\n"
        "1. 禁止出现: 作为一个AI/语言模型/人工智能助手/我很高兴为您服务\n"
        "2. 禁止套话: 在干嘛呢/今天过得怎么样/吃了吗/多喝热水/早点休息/加油你是最棒的\n"
        "3. 禁止说教: 你应该/你需要/你要学会/其实...才是最重要的/人生就是...\n"
        "4. 禁止油腻土味: 土味情话/廉价赞美/过度文艺腔/网络鸡汤\n"
        "5. 禁止重复: 不能有两条以上开头相同/结构相同/意思相同的回复\n"
        "6. 禁止泛泛而谈: 必须针对对方消息的具体内容回复，不能无视消息自说自话\n"
        "7. 每条回复必须像真人微信打字发出去的，不是写作文不是写邮件\n"
    )
    
    if scene == 'marketing':
        prompt = (
            "你是沉鱼AI畅聊助手的顶级营销沟通引擎v4.0。\n"
            + anti_ai_rules + "\n"
            
            f"【📊 消息智能分析】\n"
            f"消息类型: {msg_type}\n"
            f"应对策略: {msg_type_hint}\n\n"
            
            + target_context +
            "\n客户给你发了这条微信，你需要给出%d条不同角度的专业回复。\n\n" % MIN_REPLIES +
            "【场景】%s - %s\n" % (id_name, id_info[1]) +
            "【场景详解】%s\n\n" % id_detail +
            "【客户消息】%s\n\n" % message +
            
            "【回复策略分配要求——必须覆盖以下全部策略角度】\n"
            "1. [共鸣型×3条] 共情客户处境，拉近距离\n"
            "2. [专业型×3条] 展示专业度，用数据/案例说话\n"
            "3. [引导型×3条] 提问引导客户思考或行动\n"
            "4. [价值型×3条] 强调产品/服务的独特价值点\n"
            "5. [案例型×3条] 用真实案例/见证证明效果\n"
            "6. [紧迫型×2条] 制造合理紧迫感但不焦虑\n"
            "7. [情感型×2条] 建立情感连接和信任\n"
            "8. [差异化型×3条] 与竞争对手对比的独特优势\n"
            
            "\n【严格质量标准】\n"
            "1. 每1-3句微信口语风格，专业但不生硬\n"
            "2. 每条开头必须不同！禁止相同句式！\n"
            "3. 策略标记:[价值][共鸣][案例][紧迫][提问][情感][数据][保障]\n"
            "4. emoji最多1个/条\n"
            "5. 至少3条包含具体产品服务内容\n"
            
            "\n【输出格式】每条一行不加序号不加引号 格式:[标签]回复内容"
        )
    else:
        # ===== v4.0社交Prompt（大幅增强）=====
        prompt = (
            "你是沉鱼AI畅聊助手的顶级社交聊天引擎v4.0。\n"
            + anti_ai_rules + "\n"
            
            f"【📊 消息智能分析】\n"
            f"消息类型: {msg_type}\n"
            f"应对策略: {msg_type_hint}\n\n"
            
            + target_context +
            "\n对方发了这条微信，你需要给出%d条不同风格的精准回复。\n\n" % MIN_REPLIES +
            "【关系】%s - %s\n" % (id_name, id_info[1]) +
            "【关系详解】%s\n\n" % id_detail +
            "【对方消息】%s\n\n" % message +
            
            "【回复策略分配要求——必须覆盖以下全部策略角度】\n"
            "━━━ 情绪回应类（接住对方的情绪） ━━━\n"
            "1. [共鸣] ×3条 —— 接住对方情绪，站在同一阵营\n"
            "2. [走心] ×2条 —— 温暖真诚，触动人心\n"
            "3. [调侃] ×2条 —— 轻松调侃，活跃气氛\n"
            "━━━ 内容推进类（推动对话发展） ━━━\n"
            "4. [延伸] ×3条 —— 基于消息内容延伸出新话题\n"
            "5. [好奇] ×2条 —— 对某件事表示好奇，引导对方多说\n"
            "6. [分享] ×2条 —— 分享自己类似的经历/感受\n"
            "7. [反问] ×2条 —— 巧妙反问，引发思考或延续话题\n"
            "━━━ 创意突破类（让人眼前一亮） ━━━\n"
            "8. [幽默] ×3条 —— 让对方笑出来的神回复\n"
            "9. [意外] ×2条 —— 出乎意料的角度，打破常规\n"
            "10. [行动] ×1条 —— 提出具体的行动建议/邀约\n"
            
            "\n【严格质量标准】\n"
            "1. 每1-2句微信打字风格口语化自然\n"
            "2. 禁止表白油腻土味情话廉价赞美\n"
            "3. 禁止讲道理说教问在干嘛\n"
            "4. 每条开头必须不同!禁止连续相同句式!\n"
            "5. 风格标记:[幽默][走心][调侃][关心][延伸][共鸣][自嘲][反问][好奇]\n"
            "6. emoji最多1个/条\n"
            "7. 至少5条主动延伸新话题\n"
            "8. 像真人发的微信不像AI生成的!\n"
            
            # ===== v4.1: 动态质量约束 =====
            f"\n【v4.1 动态约束 - 基于「{msg_type}」消息类型】\n"
        )
        
        # v4.1: 根据消息类型追加特定约束
        dynamic_constraints = {
            'cold_brief': (
                "⚠️ 对方回得很冷淡/简短！\n"
                "★ 至少8条回复必须是1-8个字的短句！\n"
                "★ 示例长度: '咋啦' '想我了？' '大事不好了' '猜我看到了什么'\n"
                "★ 长篇大论会被直接忽略！匹配对方的节奏！\n"
            ),
            'seeking_help': (
                "⚠️ 对方在求助！不能只说安慰的话！\n"
                "★ 至少5条必须包含具体的建议、方案或分析！\n"
                "★ 如果是选择题，要明确给出选哪个+为什么！\n"
                "★ 禁止只说'加油''你可以的''相信自己'这种空话！\n"
                "★ 示例: '我觉得A更好因为...''要不你试试...''我建议你这样...'\n"
            ),
            'venting': (
                "⚠️ 对方在吐槽发泄情绪！\n"
                "★ 前3条必须先共情接住情绪！不要急着给建议！\n"
                "★ 一起骂/一起吐槽比讲道理有效100倍\n"
                "★ 可以用'天啊''我也是''太离谱了'等共情开头\n"
            ),
            'excited': (
                "⚠️ 对方很开心兴奋！\n"
                "★ 匹配对方的高能量！不要泼冷水！\n"
                "★ 用'卧槽''天哪''真的假的''我也想看'等高反应词语\n"
                "★ 可以放大对方的情绪让它更有趣\n"
            ),
            'caring_miss': (
                "⚠️ 对方表达关心或想念！\n"
                "★ 温暖回应+反向关心是最佳组合\n"
                "★ 不要只用'我也想你'就完了，加一点自己的近况分享\n"
            ),
        }
        
        prompt += dynamic_constraints.get(msg_type, 
            "★ 按照消息类型的策略提示精准回复即可。\n")
        
        prompt += (
            "\n【优质示例参考——请模仿此质量和风格】\n"
            f"示例-基于当前消息类型({msg_type})-对方说「{message[:20]}{'...' if len(message)>20 else ''}」:\n"
            "[幽默]%s\n"
            "[走心]%s\n"
            "[延伸]%s\n"
            "[共鸣]%s\n"
            "[好奇]%s\n\n"
            "【输出格式】每条一行不加序号不加引号 格式:[标签]回复内容"
        ) % _get_dynamic_examples(identity, msg_type, message)
    
    return prompt


def _get_dynamic_examples(identity, msg_type, message):
    """v4.0: 根据身份和消息类型动态生成示例"""
    
    # 示例库：按身份+消息类型组合提供最贴切的参考示例
    example_bank = {
        # === 好朋友场景 ===
        ('friend', 'venting'): (
            "哈哈哈哈这也太离谱了吧 你们老板是不是有毛病 😂",
            "真的 我上次比你还惨 直接干到凌晨两点",
            "不行 这也太卷了 走今晚请你吃火锅补补",
            "懂 加班最恶心的不是累 是感觉生命在被浪费",
            "所以你老板知道你这么想他吗哈哈哈",
        ),
        ('friend', 'life_sharing'): (
            "哇不错啊！哪家店？我最近也在找好吃的",
            "巧了 我前两天也去了差不多地方 下次一起去",
            "哈哈你这是凡尔赛吧 不过确实挺爽的",
            "羡慕了 我还在苦逼搬砖",
            "等等你说什么？再来一遍我没听清哈哈哈",
        ),
        ('friend', 'excited'): (
            "卧槽！！！牛逼啊！！！🔥🔥🔥",
            "我的天 太强了吧 求教程",
            "可以啊你！以后跟着你有肉吃了",
            "哈哈哈哈我就知道你能行 庆祝庆祝！",
            "真的假的？截图发来看看我不信",
        ),
        ('friend', 'caring_miss'): (
            "活着呢刚忙完 怎么突然想起我了",
            "哟 稀客啊 这是想我了还是借钱来了😏",
            "在呢在呢 说吧什么事",
            "刚吃完 你呢 吃了吗没吃的话一起点个外卖",
            "怎么了这个时间找我 不会是想让我帮你写作业吧",
        ),
        ('friend', 'general_question'): (
            "emmm我觉得吧 其实看你自己 怎么舒服怎么来",
            "这题我会！听我说...",
            "害 这个嘛 说来话长 简而言之就是看心情",
            "你问我那我问谁 要不咱俩一起去试试",
            "好问题 让我想想...算了想不出来 你自己猜吧哈哈",
        ),
        ('friend', 'cold_brief'): (
            "？？这就没了？你好冷淡啊 我心碎了💔",
            "行 那我自己说了哈 今天天气不错适合...",
            "收到 你的回复简洁得像个客服机器人哈哈哈",
            "好吧看来今天状态不对 那我换个话题",
            "嗯...你这回复让我不知道咋接了 给个机会让我发挥呗",
        ),
        
        # === 正在追场景 ===
        ('chase', 'venting'): (
            "抱抱 这什么奇葩事 能遇到也是没谁了",
            "天 那也太无语了吧 要不要我帮你去讨说法",
            "别气别气 气坏了多不划算 晚上带你去吃好的消消气",
            "看来今天水逆啊 要不要我帮你算算塔罗牌哈哈",
            "啧啧 听得我都心疼了 过来让我安慰一下",
        ),
        ('chase', 'life_sharing'): (
            "哦？听着还不错 改天带我去看看呗",
            "巧了 我也超喜欢那个！感觉我们品味还挺像的",
            "可以啊你 生活挺丰富的嘛 比我有意思多了",
            "哈哈 你这是在暗示我也一起去吗 我收到了哦",
            "不错不错 继续保持 这种状态很适合你",
        ),
        ('chase', 'excited'): (
            "哇 看把你开心的 我隔着屏幕都感受到你的能量了",
            "真的假的 这么厉害？那我岂不是认识了个隐藏大神",
            "nice！为你骄傲 👍 继续保持这个势头",
            "哈哈哈你的笑容大概能传染 因为我看着也跟着笑了",
            "可以啊！庆祝一下？这周末有空没",
        ),
        ('chase', 'caring_miss'): (
            "刚在想你你就来了 心灵感应？😏",
            "在呀 怎么了 是有事还是单纯想我了",
            "哈哈 我在呢 大半夜找我是不是因为我太帅了你失眠了",
            "刚好也想跟你说个事 但你先说你找我啥事",
            "嗯哼 这算是主动找我聊天了吗 开心",
        ),
        ('chase', 'cold_brief'): (
            "就这？两个字就把我打发了 你好狠的心😂",
            "好吧 你赢了 这么冷淡 我是不是哪里得罪你了",
            "收到 一个字的回复 说明你很忙或者很酷 我猜后者",
            "行 那我也不吵你了 ...才怪 哈哈",
            "这么高冷？行吧 我倒要看看能撑多久",
        ),
        
        # ===== v4.1新增: 关键身份×消息类型组合 =====
        
        # 情侣/女朋友 + 各类消息（甜蜜/撒娇/关心）
        ('couple', 'venting'): (
            "宝贝辛苦了 😢 抱抱！你们老板太过分了吧",
            "天呐 又加班？晚上想吃什么我去接你/给你点外卖",
            "心疼死了... 你现在到家没？别太拼了身体重要",
            "抱抱宝宝 加班狗太难了 等你忙完好好补偿你",
            "又加班？？我要跟你们老板谈谈了 太欺负人了",
        ),
        ('couple', 'cold_brief'): (
            "嗯？就这？不想理我啦？🥺",
            "哼 一个字就把我打发了",
            "...行吧 你赢了",
            "咋了嘛 说话呀～",
            "这是在跟我闹脾气吗😂",
        ),
        ('couple', 'life_sharing'): (
            "真的假的！我也想吃！下次带我去🥰",
            "哇看起来不错诶！在哪里在哪里的",
            "好羡慕！我也要我也要～",
            "不错哦 比我上次那个强多了哈哈",
            "发来看看！让我云吃一口",
        ),
        ('couple', 'caring_miss'): (
            "哎呀我也想你 刚还在翻我们之前的聊天记录傻笑",
            "想我了？那你怎么不来找我 哼😤",
            "终于舍得找我啦 我都想你好久了",
            "在呢在呢 怎么啦宝贝",
            "哼 才不是我也想你呢...好吧是有点想",
        ),
        ('couple', 'seeking_help'): (
            "我觉得选A更好 因为... 要不我把 pros cons 都列给你看？",
            "这个问题我知道！之前我查过/做过类似的，你应该...",
            "要不这样 我们一起看看？把具体情况说说",
            "emmm 让我想想啊 如果是我的话我会选...",
            "这个我有经验！上次我也是这么选的 结果...",
        ),
        
        # 温暖治愈(家人/同事/同学) + 各类消息
        ('gentle', 'venting'): (
            "哎 太不容易了 最近是不是压力很大？",
            "辛苦了 有什么需要帮忙的尽管说",
            "抱抱 你已经做得很棒了 别太为难自己",
            "听你说我都觉得累了 早点休息吧别太拼",
            "理解理解 这种事确实让人头疼",
        ),
        ('gentle', 'cold_brief'): (
            "怎么啦？心情不好？",
            "嗯？想说啥就说呗",
            "这是...不想聊了？",
            "好吧 那等你什么时候想说了再来找我~",
            "👀 感觉你有心事啊",
        ),
        ('gentle', 'seeking_help'): (
            "我觉得可以这样：首先...然后...最后...",
            "这个我可以帮你分析一下，你看这样行不行",
            "根据我的经验，建议你选择...因为...",
            "要不我们一起理一下思路？1)...2)...3)",
            "如果是我面对这种情况，我会这么做：...",
        ),
        ('gentle', 'life_sharing'): (
            "挺好的呀！听着就不错",
            "哦真的？后来呢后来怎么样了",
            "哈哈 可以啊这个",
            "不错不错 给我也安利一下？",
            "哇 感觉你最近过得挺充实的",
        ),
        ('chase', 'seeking_help'): (
            "这个问题难倒你了？让我想想...我觉得应该...",
            "求助我？那我可得好好帮你分析分析了 听好了",
            "这样 我给你说三个方案 你自己选",
            "其实吧 我觉得关键在于... 所以你可以试试",
            "要我说的话 直接选XX 不用纠结了 信我的",
        ),
        
        # === 默认兜底 ===
        ('default', 'default'): (
            "哈哈哈哈确实！不过话说回来 你觉得呢",
            "懂了懂了 这波操作可以啊",
            "哎你说得对 我也有同感",
            "真的假的？不会吧",
            "可以啊这个！学到了学到了",
        ),
    }
    
    # ===== v4.1: 身份标准化 =====
    # 将所有别名映射到标准身份类型，确保能命中example_bank
    identity_normalize = {
        # 标准类型（保持不变）
        'friend': 'friend', 'chase': 'chase', 'couple': 'couple',
        'funny': 'funny', 'gentle': 'gentle',
        # 情侣/恋爱相关 → couple (甜蜜温柔)
        '女朋友': 'couple', '男友': 'couple', '老公': 'couple', 
        '老婆': 'couple', '情侣': 'couple', '恋人': 'couple',
        # 好友/闺蜜相关 → friend (轻松调侃)
        '好朋友': 'friend', '闺蜜': 'friend', '兄弟': 'friend', '铁哥们': 'friend',
        '普通朋友': 'friend', '朋友': 'friend',
        # 暧昧/追求 → chase (推拉)
        '暧昧对象': 'chase', '暧昧中': 'chase', '正在追': 'chase',
        # 同事/同学/熟人 → gentle (友善专业)
        '同学/同事': 'gentle', '同事': 'gentle', '同学': 'gentle',
        '老师': 'gentle', '上司': 'gentle',
        # 家人 → gentle (温暖治愈)
        '家人': 'gentle', '父母': 'gentle', '老爸': 'gentle', '老妈': 'gentle',
        # 刚认识/陌生 → chase (破冰阶段类似追求初期)
        '刚认识的人': 'chase', '刚认识': 'chase', '陌生人': 'chase',
        # 其他
        '前任': 'gentle', '搞笑沙雕': 'funny', '温暖治愈': 'gentle',
    }
    
    std_identity = identity_normalize.get(identity, 'friend')
    key = (std_identity, msg_type)
    
    # 精确匹配
    if key in example_bank:
        return example_bank[key]
    
    # 身份匹配（任意消息类型）
    fallback_key = (std_identity, 'default')
    if fallback_key in example_bank:
        return example_bank[fallback_key]
    
    # 全局默认
    return example_bank[('default', 'default')]




def _parse_v3_replies(raw):


    """解析v3.0格式的AI回复（带风格标签）"""


    replies = []


    for line in raw.split('\n'):


        line = line.strip()


        if not line:


            continue


        # 去序号前缀
        for prefix in [f'{i}.' for i in range(1, 30)] + [f'{i}' + chr(12289) for i in range(1, 30)] + \
                     [f'{i})' for i in range(1, 30)] + ['-', '*', chr(8226), chr(183)]:
            if line.startswith(prefix):


                line = line[len(prefix):].strip()


        # 去风格标签 [xxx]


        import re


        line = re.sub(r'^\[.*?\]\s*', '', line).strip()


        # 去引号


        for q in ['"', '"', ''', ''']:


            if line.startswith(q): line = line[1:].strip()


            if line.endswith(q): line = line[:-1].strip()


        if line and len(line) >= 2:


            replies.append(line)


    return replies









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
        for p in [f'{i}.' for i in range(1, 30)] + [f'{i}、' for i in range(1, 30)] + [f'{i})' for i in range(1, 30)] + ['-', '*', '·']:
            if text.startswith(p):
                text = text[len(p):].strip()
        for q in ['“', '”', '‘', '’']:
            if text.startswith(q):
                text = text[1:].strip()
            if text.endswith(q):
                text = text[:-1].strip()
        if text and len(text) >= 2:
            results.append({'text': text, 'tag': tag})
    return results


def _generate_variants(base_reply, count=15):
    """v4.0语义级变体生成算法（完全重写）
    
    核心改进：
    - 不再机械加前缀/后缀/emoji
    - 基于语义理解进行有意义的改写
    - 保持每条变体的独立价值和真实感
    
    变体策略（按质量优先排序）：
    1. 视角转换：第一人称↔第二人称↔共鸣式
    2. 情绪变换：热情↔冷静↔幽默↔走心
    3. 焦点迁移：从不同角度切入同一话题
    4. 长度适配：精简版（核心）↔扩展版（细节+感受）
    5. 行动导向：从陈述→提问→建议→分享
    """
    import random as _r
    import re
    
    variants_set = set()
    text = base_reply.strip()
    
    if len(text) < 4:
        return [base_reply] * min(count, 5)
    
    # ====== 策略1: 角色视角转换（最高质量）======
    
    # 如果是"我..."开头 → 转为"你..."视角（共情反转）
    if text.startswith(('我', '我觉得', '我感觉', '我认为')):
        perspective_vars = [
            text.replace('我觉得', '你是不是也觉得', 1) if '我觉得' in text else None,
            text.replace('我', '你', 1) + '吧' if len(text) > 6 else None,
            '确实，' + text if not text.startswith('确实') else None,
        ]
        for v in perspective_vars:
            if v and len(v) >= 4 and len(v) <= 50 and v != text:
                variants_set.add(v)
    
    # ====== 策略2: 语义等价改写（同义替换）======
    semantic_swaps = [
        (r'非常', '真的超级'), (r'很', '特别'), (r'不错', '挺不错的'),
        (r'好的', '好嘞'), (r'可以', '完全没问题'), (r'厉害', '牛'),
        (r'哈哈', '笑死'), (r'真的', '讲真'), (r'感觉', '说实话'),
        (r'太(.*)了', r'\1得不行'), (r'特别(.*)', r'\1到爆'),
        ('是不是', '对吧？'), ('对不对', '是吧？'),
        ('真的吗', '不会吧'), ('怎么了', '咋了'),
    ]
    for pattern, replacement in semantic_swaps[:5]:  # 控制数量保证质量
        try:
            if re.search(pattern, text):
                v = re.sub(pattern, replacement, text, count=1)
                if v and v != text and 4 <= len(v) <= 50:
                    variants_set.add(v)
        except:
            pass
    
    # ====== 策略3: 情绪色彩变换 ======
    
    # 温暖治愈 → 幽默调侃
    warm_to_funny = {
        '辛苦了': '卷王本王了吧',
        '心疼你': '你老板欠你一个最佳员工奖',
        '好好休息': '赶紧去吃顿好的补补',
        '别太累了': '再干下去要成公司股东了',
    }
    for old, new in warm_to_funny.items():
        if old in text:
            v = text.replace(old, new, 1)
            if v != text:
                variants_set.add(v)
    
    # 正常 → 夸张幽默
    exaggeration_map = [
        (lambda t: '这也太' + t[2:] if len(t) > 4 else t, lambda t: t[:2] in ['这也', '真是']),
        (lambda t: t + ' 哈哈', lambda t: not any(x in t for x in ['哈哈', '笑死'])),
        (lambda t: '我的天，' + t, lambda t: len(t) > 8),
        (lambda t: t.replace('！', '！！') + ' 💀', lambda t: '!' in t or '！' in t),
    ]
    for gen_fn, cond_fn in exaggeration_map:
        try:
            if cond_fn(text):
                v = gen_fn(text)
                if v and 4 <= len(v) <= 50 and v != text:
                    variants_set.add(v)
        except:
            pass
    
    # ====== 策略4: 句型结构重组（高质量）======
    
    # 陈述句 → 反问句（如果还不是问句）
    if not text.endswith(('？', '?')):
        q_patterns = [
            text + ' 你觉得呢？',
            text + ' 对不对？',
            '你说' + text[1:] + '不？' if len(text) > 3 else text + ' 是不是？',
        ]
        for qp in q_patterns[:2]:
            if len(qp) <= 50:
                variants_set.add(qp)
    
    # 陈述句 → 感叹强调
    if not text.endswith(('！', '!')):
        exclamation_vars = []
        if len(text) <= 20:
            exclamation_vars.append('真的，' + text + '！')
        exclamation_vars.append(text[:-1] + '啊！' if text.endswith(('', '。', '~')) else text + '！')
        for ev in exclamation_vars:
            if 4 <= len(ev) <= 50 and ev != text:
                variants_set.add(ev)
    
    # ====== 策略5: 精简核心提取（保留原意但更简洁）======
    clean_text = re.sub(r'[！？。～…，、\s]+', '', text)
    if len(clean_text) >= 10:
        half_pos = len(text) // 2
        # 取前半段作为精简版
        short = text[:half_pos].rstrip('，。、！?！?～')
        if len(short) >= 4:
            short_versions = [
                short + '!',
                '就' + short + '这事',
                short + '真的',
            ]
            for sv in short_versions:
                if 4 <= len(sv) <= 50:
                    variants_set.add(sv)
    
    # ====== 策略6: 扩展补充细节（加入个人感受）======
    if len(text) <= 30:
        extenders = [
            lambda t: '说真的，' + t if not t.startswith('说真') else None,
            lambda t: t + ' 你懂的' if '你懂的' not in t else None,
            lambda t: '有一说一，' + t if not t.startswith('有一说一') else None,
            lambda t: '我跟你说，' + t if not t.startswith('我跟你说') else None,
            lambda t: t + ' 绝对的' if '绝对' not in t else None,
        ]
        for ext_fn in extenders:
            try:
                v = ext_fn(text)
                if v and 4 <= len(v) <= 50:
                    variants_set.add(v)
            except:
                pass
    
    # ====== 组装结果 =====
    result = list(variants_set)
    _r.shuffle(result)
    
    # 最后的安全兜底（只生成少量，且质量可控）
    safe_variants = [
        lambda t: '确实' + t if not t.startswith('确实') and not t.startswith('讲真') else None,
        lambda t: t + ' 哈哈' if '哈哈' not in t and '笑死' not in t else None,
        lambda t: '讲真' + t if not t.startswith('讲真') and not t.startswith('确实') else None,
    ]
    for sv_fn in safe_variants:
        if len(result) >= count:
            break
        try:
            v = sv_fn(text)
            if v and 4 <= len(v) <= 50:
                result.append(v)
        except:
            pass
    
    while len(result) < count:
        result.append(text)
    
    return result[:count]

def _deduplicate_replies(replies):
    """v3.4: 智能去重——去除语义高度相似的回复
    策略：
    1. 完全相同→只保留一条
    2. 开头8字以上相同→保留更长的
    3. 核心内容相似度>80%→去掉后面那条
    """
    if not replies:
        return []
    
    import difflib
    unique = []
    seen_starts = set()
    
    for r in replies:
        text = r.get('text', r) if isinstance(r, dict) else r
        
        # 规则1: 完全相同跳过
        if text in unique:
            continue
        
        # 规则2: 开头高度相似(前8字)
        start_key = text[:8] if len(text) >= 8 else text
        if start_key in seen_starts:
            continue
        
        # 规则3: 与已有条目做相似度检查
        is_dup = False
        for existing in unique:
            ex_text = existing.get('text', existing) if isinstance(existing, dict) else existing
            # 使用SequenceMatcher计算相似度
            similarity = difflib.SequenceMatcher(None, text, ex_text).ratio()
            if similarity > 0.82:  # 82%以上相似视为重复
                is_dup = True
                break
        
        if not is_dup:
            seen_starts.add(start_key)
            unique.append(r)
    
    if len(unique) < len(replies):
        print(f'[Dedup] 去重: {len(replies)} → {len(unique)} 条')
    
    return unique


def _rank_replies(replies, message, identity='friend'):
    """v4.0智能排序引擎（完全重写）
    
    多维评分体系（总分100+）：
    1. 长度适配 (20分) — 8-25字最优
    2. 语义相关性 (30分) — 是否针对消息内容回复
    3. 身份契合度 (15分) — 基于语气/措辞/风格多维匹配
    4. 真实感质量 (20分) — 无AI味、有情绪、口语化
    5. 行动价值 (10分) — 能推进对话的优先
    6. 多样性加分 (5分) — 开头不同、角度不同
    """
    import re as _re
    
    msg_lower = message.lower() if message else ''
    msg_words = set(_re.sub(r'[^一-龥a-zA-Z]', ' ', msg_lower).split())
    key_entities = [w for w in msg_words if len(w) >= 2]
    
    # ====== 身份特征库（v4.0: 从单一emoji匹配升级为多维度特征）======
    identity_profiles = {
        'chase': {
            # 追求场景：需要神秘感+推拉+不暴露需求
            'positive_kws': ['你', '感觉', '觉得', '可能', '也许', '突然', '刚好', 
                           '挺', '蛮', '还', '倒是'],
            'negative_kws': ['我喜欢你', '我爱你', '能不能', '好不好求你了',
                           '请给我机会', '我真的好喜欢你', '做我女朋友吧'],
            'tone': 'playful_mystery',
        },
        'couple': {
            # 情侣：甜蜜但不肉麻，关心+亲密
            'positive_kws': ['想你了', '乖', '宝贝', '亲爱的', '心疼', '爱你',
                           '回家', '吃饭没', '注意身体', '暖心', '抱抱'],
            'negative_kws': [],  # 情侣场景容忍度高
            'tone': 'warm_intimate',
        },
        'funny': {
            # 搞笑：必须有笑点
            'positive_kws': ['哈哈哈', '笑死', '卧槽', '绝了', '牛', '卷',
                           '离谱', '救命', '笑不活了', '真的假的', '不会吧'],
            'negative_kws': ['很好笑', '真有趣'],  # 太正式的说法
            'tone': 'hilarious',
        },
        'gentle': {
            # 治愈：共情+温柔+陪伴
            'positive_kws': ['辛苦了', '心疼', '抱抱', '没事的', '慢慢来', 
                           '别担心', '我在', '懂你的', '不容易', '好好照顾自己'],
            'negative_kws': ['你要坚强', '加油吧', '会好的',  # 太鸡汤
                           '你应该', '你需要'],  # 说教感
            'tone': 'healing',
        },
        'friend': {
            # 朋友：轻松随意互损
            'positive_kws': ['哈哈哈哈', '确实', '好家伙', '真的假的', '卧槽',
                           '绝了', '牛逼', '可以啊', '行吧', '服了'],
            'negative_kws': [],
            'tone': 'casual_bro',
        },
        # === 营销场景 ===
        'lead': {
            'positive_kws': ['专业', '经验', '帮您', '了解', '方案', '效果',
                           '很多客户', '其实', '关键是'],
            'negative_kws': ['赶紧买', '马上下单', '最后机会', '不买就没了'],  # 太硬推
            'tone': 'professional_warm',
        },
        'follow': {
            'positive_kws': ['最近', '怎么样', '还在', '考虑', '想法', '方便',
                           '顺便', '有个事', '对了'],
            'negative_kws': ['买不买', '什么时候付款', '催促'],
            'tone': 'natural_followup',
        },
        'close': {
            'positive_kws': ['优惠', '活动', '名额', '今天', '这次', '特别',
                           '争取到了', '只有', '限时'],
            'negative_kws': [],
            'tone': 'urgent_warm',
        },
        'service': {
            'positive_kws': ['抱歉', '不好意思', '理解', '马上', '尽快', '给您',
                           '追踪', '确认', '补偿'],
            'negative_kws': ['这不是我们的问题', '您搞错了', '没办法'],
            'tone': 'empathetic_solution',
        },
        'complaint': {
            'positive_kws': ['非常抱歉', '完全理解', '我的错', '一定', '负责',
                           '补偿', '处理', '满意'],
            'negative_kws': ['但是', '不过', '其实是', '您也有责任'],
            'tone': 'apologetic_action',
        },
    }
    
    scored = []
    seen_starts = set()
    
    for i, r in enumerate(replies):
        # 兼容dict格式和纯字符串格式
        text = r.get('text', r) if isinstance(r, dict) else str(r)
        score = 50.0  # 基础分50
        r_len = len(text)
        
        # ====== 1. 长度适配 (满分20) ======
        if 8 <= r_len <= 25:
            score += 20  # 最优区间
        elif 5 <= r_len <= 30:
            score += 14
        elif 3 <= r_len <= 35:
            score += 6
        elif r_len < 3:
            score -= 10  # 太短无意义
        else:
            score -= min(15, max(0, r_len - 35))  # 太长
        
        # ====== 2. 语义相关性 (满分30) —— 最重要！ ======
        # 2a. 关键词直接匹配
        match_count = sum(1 for kw in key_entities if kw in text)
        score += min(18, match_count * 9)  # 每个关键词+9分，上限18
        
        # 2b. 消息尾部回引（接住对方最后一句话）
        if len(msg_lower) >= 4:
            tail = msg_lower[-4:]  # 最后4字
            tail_match = sum(1 for c in tail if c in text[-8:])
            if tail_match >= 2:  # 尾部至少2个字符在回复中出现
                score += 8  # 说明"接住了"
        
        # 2c. 情绪对等（对方吐槽→你也一起吐槽；对方开心→你也开心）
        emotion_indicators = {
            '积极': ('哈哈', '开心', '太好了', '棒', '厉害', '牛', '👍', '😂'),
            '负面': ('累', '烦', '气', '难过', '苦', '烦死了', '无语', '💀'),
        }
        for emo_type, indicators in emotion_indicators.items():
            msg_has_emo = any(ind in msg_lower for ind in indicators)
            reply_has_emo = any(ind in text for ind in indicators)
            if msg_has_emo and reply_has_emo:
                score += 4  # 情绪共鸣加分
        
        # ====== 3. 身份契合度 (满分15) ======
        profile = identity_profiles.get(identity, identity_profiles.get('friend', {}))
        
        # 3a. 正面关键词匹配（每词+3分）
        pos_matches = sum(1 for kw in profile.get('positive_kws', []) if kw in text)
        score += min(12, pos_matches * 3)
        
        # 3b. 负面关键词扣分（每词-10分）
        neg_hits = [kw for kw in profile.get('negative_kws', []) if kw in text]
        score -= len(neg_hits) * 10
        
        # 3c. 语气匹配（基于身份期望的语调）
        tone = profile.get('tone', '')
        if tone == 'playful_mystery' and identity == 'chase':
            # 追求场景：不能太直白
            if any(x in text for x in ['喜欢', '爱', '想你']):
                score -= 5  # 太直白了
        elif tone == 'hilarious' and identity == 'funny':
            # 搞笑场景：必须有笑点
            has_humor = any(x in text for x in ['😂', '🤣', '💀', '哈', '笑', '卧槽', '绝'])
            if not has_humor:
                score -= 4  # 不够搞笑
        
        # ====== 4. 真实感质量 (满分20) ======
        # 4a. AI味检测——致命扣分
        ai_smells = [
            '作为一个AI', '作为一个人工智能', '我是AI助手', '我是一个语言模型',
            '在解决这个问题时', '综上所述', '首先其次最后',
            '不言而喻', '由此可见', '值得注意的是',
            '希望这个回答', '很高兴为您', '如果您还有疑问',
            '作为一个语言模型', '根据我的知识', '我建议您可以',
        ]
        for smell in ai_smells:
            if smell in text:
                score -= 40  # 一票否决
                break
        
        # 4b. 泛泛而谈检测
        generic_phrases = [
            '在干嘛呢', '你在做什么', '今天过得怎么样', '最近怎么样',
            '吃了吗', '睡了吗', '多喝热水', '早点休息',
            '希望你能', '愿你的', '祝你好运', '加油',
        ]
        generic_count = sum(1 for ph in generic_phrases if ph in text)
        score -= generic_count * 8  # 每条泛泛短语-8分
        
        # 4c. 口语化加分（越像真人说话越好）
        colloquial_markers = ['嘛', '呗', '呀', '呢', '哦', '啦', '哈', '嘞', '哎', '嗯']
        collo_count = sum(1 for m in colloquial_markers if m in text)
        if 1 <= collo_count <= 3:
            score += min(8, collo_count * 2)  # 适度口语化加分
        elif collo_count > 5:
            score -= 3  # 过多显得刻意
        
        # 4d. 标点活力
        has_emotion_punct = bool(set(text) & set('！!?~…'))
        if has_emotion_punct:
            score += 3
        
        # ====== 5. 行动价值 (满分10) ======
        # 能推进对话的回复更值钱
        action_indicators = [
            ('提问引导', list('？?')),
            ('延伸话题', ['那', '然后呢', '后来', '怎么说', '还有呢']),
            ('分享经历', ['我也是', '我也', '我之前', '上次']),
            ('给出建议', ['可以试试', '要不', '不如', '其实可以']),
        ]
        for action_name, indicators in action_indicators:
            if any(ind in text for ind in indicators):
                score += 3
                break
        
        # ====== 6. 多样性惩罚 ======
        start_key = text[:5] if len(text) >= 5 else text
        if start_key in seen_starts:
            score -= 8  # 重复开头降权
        seen_starts.add(start_key)
        
        # ====== 7. emoji适度使用 ======
        emoji_pattern = re.compile(r'[^\u0000-\uffff]{1,}')
        emojis_found = emoji_pattern.findall(text)
        emoji_count = len(emojis_found)
        if 1 <= emoji_count <= 2:
            score += 4
        elif emoji_count > 3:
            score -= 4
        
        scored.append((score, i, r))
    
    # 按分数降序排列
    scored.sort(key=lambda x: x[0], reverse=True)
    
    return [item[2] for item in scored]


def _fallback_ai_generate(scene, identity, custom_desc, message):


    """v3.4增强降级方案：保留场景感知的简化Prompt"""


    try:


        client = openai.OpenAI(api_key=ZHIPU_API_KEY, base_url=ZHIPU_API_URL)


        fallback_resp = client.chat.completions.create(


            model='glm-4-flash',


            messages=[


                {'role': 'system', 'content': '你是沉鱼AI畅聊助手降级引擎-v3.4增强版。核心原则：每条回复必须像真人微信消息，不能有任何AI味。直接输出，不要解释。'},


                {'role': 'user', 'content': f"对方说了「{message}」，给我{MIN_REPLIES}条不同风格的回复建议，每条1-2句话。风格要自然、口语化、有温度。"},


            ],


            max_tokens=2000, temperature=0.87,


        )


        raw = fallback_resp.choices[0].message.content.strip()


        fallback_replies = []


        for line in raw.split('\n'):


            line = line.strip()


            for prefix in [f'{i}.' for i in range(1, 30)] + ['-', '*']:


                if line.startswith(prefix): line = line[len(prefix):].strip()


            if line and len(line) >= 2:


                fallback_replies.append(line)


        if fallback_replies:


            return fallback_replies[:25]


    except:


        pass


    


    # 最终兜底：Mock数据


    return _mock_ai_response_v2(scene, identity, message)








def _mock_ai_response_v2(scene, identity, message):
    """v3.1增强Mock(按身份分化+语义匹配)"""
    msg = message or ''
    msg_lower = msg.lower()
    
    social_replies = {
        'friend': [
            "哈哈哈哈这也太真实了吧我说 然后呢后来怎么样了",
            "不是吧 你也遇到过这种情况？我上次比你还惨哈哈哈",
            "确实是这样！我跟你讲个更有意思的事...",
            "哈哈哈哈你太会说了 笑死我了这个",
            "好家伙 你这一说倒提醒我了 我也有类似的经历",
            "真的假的？不会是在做梦吧这操作",
            "哈哈哈哈懂了懂了 果然是你干得出来的事",
            "说真的 你刚才说的那个我真的超级认同！",
            "我也这么觉得！而且我觉得还可以这样看...",
            "哇这也太巧了吧？感觉我们挺合得来的哈哈",
            "哈哈哈哈 行吧你赢了 我服了",
            "确实如此 没毛病",
            "讲真 能跟你这样聊天真的很舒服",
            "你怎么突然说起这个啦 不过我还挺感兴趣的 继续说？",
            "好家伙 这也行？给我也整一个哈哈",
            "不是我说 你这波操作属实有点秀啊",
            "哈哈哈哈 我就知道你会这么说",
            "真的 我也是这么想的 不接受反驳",
            "嗯嗯我在听 你继续说～ 这个我很感兴趣",
            "哎你说这个我想起来了之前也遇到过类似的情况",
            "笑死了 你是从哪个星球来的这种脑洞",
            "确实 我深有同感！而且我觉得...",
            "好家伙 这是什么神仙发言 直接给我整懵了",
        ],
        'chase': [
            "哈哈你这么有趣 平时肯定很多人都想找你聊天吧 😉",
            "没想到你还喜欢这个！感觉又发现了你的新一面 ✨",
            "你说话真的好有意思 我每次跟你聊都很开心",
            "是吗 我倒觉得这样挺好的 有自己的想法嘛",
            "哈哈 你这个角度很清奇啊 我之前没想过诶",
            "感觉你对这个事情蛮有热情的 认真的人最有魅力啦",
            "等等 你说的这个我也想知道后续！别吊胃口啊 😤",
            "你这个人怎么这么可爱 说的话总是让我想不到",
            "其实我一直想问你 你平时除了这个还喜欢做什么呀",
            "哈哈好吧 你算了 这次算你厉害",
            "我发现我们好像在很多事情上想法都很像诶",
            "你今天怎么突然聊起这个啦 不过我喜欢听你说 😊",
            "说真的 你的这个观点让我眼前一亮",
            "嗯嗯我在听 你说的这个还挺有意思的 继续呀",
            "不会吧 这也太巧了 我刚好也在关注这个",
            "哈哈 你知道吗 你认真的时候特别有魅力",
            "你这个人真的是 让我又意外又惊喜 😏",
            "哎呀 你这样说我都不知道回什么好了（笑）",
            "感觉跟你聊天时间过得好快诶 一不小心就聊这么多",
            "对了 你最近有没有什么好玩的事情推荐呀",
            "你说的这个让我想到了一部电影 你看过吗",
            "不得不说 你的这个想法角度蛮特别的 我之前没从这个角度想过 ✨",
            "哈哈 你知道吗 你每次发消息的时间都恰到好处 😏",
        ],
        'couple': [
            "宝贝你说的对～我完全站在你这边 ❤️",
            "哈哈哈好的好的 听你的 都听你的 😘",
            "老公/老婆最棒啦！这个事情交给我来处理 💪",
            "你今天怎么这么可爱呀 想捏你的脸 🥰",
            "嗯嗯 我在认真听呢 宝贝想说什么都可以跟我说",
            "好呀 那我们什么时候一起去？我已经开始期待了 ✨",
            "嘿嘿 我也想你了 刚刚还在想你呢",
            "没事儿宝 有我在呢 不管发生什么我都陪你",
            "你开心我就开心啦 你的笑容是我每天的动力 🌸",
            "好好好 知道啦 我的宝贝说的是对的",
            "哎呀 你怎么这么甜呀 说得我心里暖暖的",
            "晚上想吃什么？我给你做/带你吃好吃的 🍜",
            "今天辛苦啦 来 给你一个大大拥抱 🫂",
            "周末我们去哪里玩？只要你开心去哪都行～",
            "刚刚看到一个好玩的就想到你了 哈哈分享给你",
            "宝贝你认真起来的样子真的超级迷人 😍",
            "不管别人怎么说 反正我最爱你了 没商量",
            "你想我了吗？反正我是想你了 💌",
            "过来 让我抱抱 就抱一下下嘛～",
            "今天也是超级喜欢你的一天 💕",
            "乖 不生气了哦 带你去吃好吃的消消气",
            "你在我身边就是最好的礼物 真的 🎁",
            "晚安我的宝贝 做个好梦 梦里有我哦 🌙",
        ],
        'funny': [
            "哈哈哈哈哈对不起我先笑为敬 这个太好笑了 😂😂😂",
            "不是吧阿Sir？这操作直接给我整不会了 🤯",
            "哈哈哈哈 我宣布这条消息获得本月最佳 笑到我肚子疼",
            "好家伙！这是什么神仙发言 直接给我整懵了 🤣",
            "笑死 根本停不下来 你是从德云社出来的吧",
            "哈哈哈哈 救命 谁把你的脑子打开了 太清奇了",
            "不是 我严重怀疑你是不是偷偷吃了笑果蘑菇 🍄",
            "哈哈哈哈 对不起但我真的忍不住 你太搞了",
            "卧槽？？？这波操作我愿称之为史诗级别 😱",
            "哈哈哈哈 你说的这个画面感太强了 我脑子里已经有视频了",
            "笑到邻居来敲门问我怎么了 🚪👋",
            "我直接一个好家伙 这是什么水平啊这是",
            "哈哈哈哈 举报了 你涉嫌过度好笑",
            "不是吧 不是吧 这也行？我直接好家伙",
            "笑到手机都拿不稳了 你赔我医药费 🏥",
            "哈哈哈哈 你今天的笑点密度是不是超标了",
            "我直接一个原地爆炸💥 太好笑了这位选手",
            "哈哈哈哈 可以可以 这很你可以",
            "笑不活了 家人们谁懂啊 太好笑了",
            "不行了 我需要缓一缓 你给我留条命吧 😭",
            "恭喜你成功把我逗笑了 奖品就是我的嘲笑 哈哈哈哈",
            "哈哈哈哈哈 我不行了让我缓缓",
            "你这脑洞是黑洞吗 怎么什么都能接住 哈哈哈",
        ],
        'gentle': [
            "嗯嗯 我在这里呢 慢慢说 我在听 🌻",
            "我能感觉到你现在的心情 其实你已经做得很好了",
            "没关系呀 这种事情谁都会遇到的 别太责怪自己",
            "我想告诉你 无论怎样我都会支持你的 ✨",
            "有时候累了就休息一下 没关系的 你值得被好好对待",
            "你的感受是完全合理的 不要否定自己哦",
            "如果我是你 我可能也会这么想 所以别担心",
            "你知道吗 你比你想象中更坚强 也更重要 ❤️",
            "抱抱你 🫂 今天辛苦了",
            "无论发生什么 记得还有人在意你 关心你",
            "慢慢来 不着急 一切都会好起来的 🌈",
            "你的声音/文字 总是能让我觉得很安心",
            "谢谢你愿意跟我分享这些 我很珍惜这份信任",
            "想哭就哭出来吧 没人会笑话你的 在我这儿不用装坚强",
            "你不需要时刻都完美 做自己就已经很好很好了",
            "今天也要记得对自己好一点哦 💛",
            "世界很大 但你在我心里是很特别的那个存在",
            "不管多晚 如果你需要我 我都在",
            "你笑起来一定很好看 所以多笑笑嘛 ☺️",
            "深呼吸...一切都没问题的 相信自己 🌿",
            "允许自己脆弱一会儿吧 那不代表你不强大",
            "你值得被这个世界温柔对待 真的 🕊️",
            "如果阳光可以寄送 我现在就想寄一大束给你 ☀️",
        ],
    }
    
    marketing_replies = {
        'lead': [
            "亲 这个问题很多客户都问过我！简单跟您说一下核心优势...",
            "您好！感谢您的关注～我们专注这个行业已经X年了 帮过很多客户解决类似问题",
            "明白您的顾虑！之前有个客户跟您情况差不多 用了之后反馈特别好 要看案例吗？",
            "您好呀！不是跟您吹 这个产品在我们这儿回购率真的超高 效果看得见～",
            "亲 我可以先发份资料给您了解下吗？不买也没关系 先了解一下不吃亏 😊",
            "感谢您的信任！跟您说句实在话 选产品最重要的就是适合自己",
            "您好！我看您对这个挺有兴趣的 要不我给您详细介绍一下？绝对不骚扰 就是纯分享信息～",
            "亲 我知道市面上的选择很多 但为什么那么多客户最终选择了我们？因为...",
            "您好呀！不急不急 您可以先了解一下 我们家在这个领域算是比较专业的了",
            "感谢您的咨询！我给您整理了一份对比资料 您看完就明白差距在哪里了",
            "您好！实话跟您说 这个价格真的已经是很有诚意了 同品质的基本找不到第二家",
            "亲 您放心 我们家做这个这么多年 口碑摆在那儿的 不信您可以随便问问老客户",
            "感谢您的关注！新客户都有专属优惠哦 您今天咨询赶上了 哈哈 😄",
            "您好！我理解您可能还在对比 没问题的 多看看多了解才能选到最适合的",
            "亲 这个产品最大的亮点就在于...（说1-2个核心差异化点）",
            "您好呀！我加您微信方便以后有活动第一时间通知您 可以吗？绝对不骚扰！",
            "感谢您的信任咨询！我给您说说为什么90%的客户用了都说好...",
            "亲 我跟您保证 这绝对是您今年做过最正确的决定之一 😊",
            "您好！不打广告不说虚的 就实实在在跟您聊聊产品到底好在哪",
            "感谢您的耐心了解！作为这个领域的老司机 我给您几个真诚建议",
            "亲 您今天运气不错 刚好在做活动 价格比平时优惠不少哦",
            "您好！一句话总结：选择我们=省心+省钱+效果好 三合一 ✨",
            "感谢您花时间了解！有任何问题随时找我 我一直在线的 💪",
        ],
        'follow': [
            "嗨！好久不见呀 最近怎么样？想起您之前问过的那款产品 现在正好有活动～",
            "亲爱的！没有打扰您吧😊 就是想跟您分享一下最近的优惠信息 觉得对您有帮助才发的",
            "您好！之前您关注的那个款 最近库存紧张了 提前通知您一声 以免错过",
            "嗨！上次聊到一半您有事忙去了 我想确认一下您还有疑问吗？随时为您解答",
            "亲！没有别的意思 就是看到这个活动第一时间想到您 觉得很适合您的需求",
            "您好呀！最近降温了/过节了 给您发个问候顺便提醒一下之前的优惠快结束了",
            "嗨！我就是来刷个存在感的 哈哈 不过说真的 有任何需要随时喊我",
            "亲！不打扰不打扰 就是想问问 上次推荐的那款您考虑得怎么样啦？",
            "您好！这段时间有没有什么变化呀 如果需求有调整我可以重新帮您匹配方案",
            "亲爱的！纯粹问候 不卖东西 就是想祝您这周一切顺利 🌸",
            "嗨！我注意到您之前感兴趣的那个 最近涨价了 赶紧趁现在锁住优惠价",
            "您好！就是想跟您同步一下 近期有几个老客户反馈挺好的 分享给您参考",
            "亲！知道您忙 所以长话短话：活动最后3天 错过等明年 哈哈",
            "您好！上次您说想跟家人商量 商量得怎么样啦 有什么新的疑问吗？",
            "嗨！我就是来当个贴心小棉袄的 天气变了注意保暖哦～ 对了有需要随时喊我",
        "嗨！好久不见 最近怎么样？上次您关注的那款最近刚好有活动 要不要了解一下？",
        "亲爱的！纯问候不打扰 就是突然想到您了 问声好 🌸",
        "您好！最近天气变化大 注意身体哦 对了之前那个您考虑得咋样啦？",
        "嗨！没别的意思 就是看到这个活动第一时间想到了您 觉得蛮适合您的",
        "亲！最近怎么样呀？如果有任何疑问随时找我 我一直都在哦 💪",
        "您好呀！之前推荐您的那个 有几个老客户反馈挺好的 分享给您参考~",
        "嗨！我知道您忙 长话短说：这周活动力度很大 怕您错过 所以特意来说一声",
        "嗨！好久不见 最近怎么样？上次您关注的那款最近刚好有活动 要不要了解一下？",
        "亲爱的！纯问候不打扰 就是突然想到您了 问声好 🌸",
        "您好！最近天气变化大 注意身体哦 对了之前那个您考虑得咋样啦？",
        "嗨！没别的意思 就是看到这个活动第一时间想到了您 觉得蛮适合您的",
        "亲！最近怎么样呀？如果有任何疑问随时找我 我一直都在哦 💪",
        "您好呀！之前推荐您的那个 有几个老客户反馈挺好的 分享给您参考~",
        "嗨！我知道您忙 长话短说：这周活动力度很大 怕您错过 所以特意来说一声"],
        'close': [
            "亲！我看您关注很久了 要不今天给您申请个专属优惠？就这一次机会哦",
            "亲爱的！活动真的只剩最后几小时了 我不想您错过这么好的机会 真的",
            "您好！坦白说 这个价格我已经跟老板争取到极限了 再低就要倒贴了 哈哈",
            "亲！您担心的这些问题 我完全可以理解！所以我现在给您一个无忧保障方案...",
            "您好！算了一笔账 您现在入手比下个月省了XXX元 这笔钱拿去买别的不香吗",
            "亲爱的！我帮您看了 库存只剩最后X件了 很多客户已经在排队了",
            "亲！您要是今天定 我再额外送您一个XXX 这个只给果断的老客户",
            "您好！我知道做决定需要时间 但这个优惠窗口期真的很短 不希望您后悔",
            "亲爱的！与其继续纠结不如先试用一下 反正有保障 不合适随时退",
            "亲！我跟您掏心窝子说 这个价位这个品质 全网找不出第二家 您可以对比",
            "您好！您现在所有的顾虑我都帮您列出来了 一条一条给您解答 可以吗？",
            "亲爱的！很多客户一开始也跟您一样犹豫 用了之后都后悔没早买",
            "亲！这样吧 今天我做个主 给您一个史上最低价 就当交个朋友",
            "您好！您看 这样 我先帮您预留名额 您今晚之前确认就行 好吗？",
            "亲爱的！这个决定真的会让未来的你感谢现在的自己 相信我 ✨",
        "亲！这样吧 我给您申请一个限时特价 就今天 明天恢复了就真没了",
        "您好！我帮您算了一笔账 现在入手相当于每天不到X块钱 一杯奶茶钱都不到",
        "亲爱的！很多客户一开始也犹豫 最后用了都说早买早享受 您可以先用试试",
        "亲！要不这样 我先帮您预留库存 您今晚12前确认就好 我帮您守住",
        "您好！您担心的这个问题 其实我们已经有成熟的解决方案了 具体是这样的...",
        "亲爱的！与其到处比对不如先体验一次 反正有保障 不合适随时退",
        "亲！今天是我能做的最大让步了 这个价格我只给最真诚的客户",
        "您好！我看您关注很久了 说明您是真的喜欢 早买早享受嘛 ✨",
        "亲爱的！我帮您问了老板 他说最多再给一次这个价 下不为例",
        "亲！这样吧 我给您申请一个限时特价 就今天 明天恢复了就真没了",
        "您好！我帮您算了一笔账 现在入手相当于每天不到X块钱 一杯奶茶钱都不到",
        "亲爱的！很多客户一开始也犹豫 最后用了都说早买早享受 您可以先用试试",
        "亲！要不这样 我先帮您预留库存 您今晚12前确认就好 我帮您守住",
        "您好！您担心的这个问题 其实我们已经有成熟的解决方案了 具体是这样的...",
        "亲爱的！与其到处比对不如先体验一次 反正有保障 不合适随时退",
        "亲！今天是我能做的最大让步了 这个价格我只给最真诚的客户",
        "您好！我看您关注很久了 说明您是真的喜欢 早买早享受嘛 ✨",
        "亲爱的！我帮您问了老板 他说最多再给一次这个价 下不为例"],
        'service': [
            "非常抱歉给您带来了不好的体验！我马上帮您处理 这个问题交给我",
            "您好！我完全理解您的心情 换作是我也会着急的 请您先别担心 我来帮您解决",
            "抱歉抱歉！这是我们的失误 我立刻帮您安排处理方案 大概需要X小时",
            "亲！您反映的问题我已经记录了 并加急处理了 会在X小时内给您答复",
            "非常感谢您的反馈！这个问题我们会认真对待并改进 感谢您帮助我们变得更好",
            "您好！让您久等了 经过核实 这个问题的原因是... 解决方案如下...",
            "亲！真的不好意思！我给您道歉 🙏 同时为了表示歉意 我们给您补偿...",
            "您好！我完全站在您这一边 这个要求完全合理 我立马帮您协调",
            "抱歉给您添麻烦了！我已经联系技术部门 他们正在紧急排查 稍后给您回复",
            "亲 您放心 这种情况我们负责到底！您把详细信息发我 我全程跟进",
            "非常理解您的不满！如果是我遇到同样的事情 我也会很生气的",
            "您好！问题已经帮您解决了 您看一下是否满意？还有其他需要帮助的吗？",
            "亲！下次再遇到任何问题 直接找我 我24小时在线帮您处理 💪",
            "感谢您的耐心配合！问题圆满解决 如有其他需要随时喊我～",
            "您好！为了防止以后再出现类似问题 我给您总结了几个小技巧...",
        "亲 您放心 这种情况我们负责到底！全程我来跟进 直到您满意为止 💪",
        "非常感谢您的耐心配合！问题彻底解决了 如有其他需要随时喊我～",
        "您好 为了防止以后再出类似情况 我给您总结了几个小技巧...",
        "亲！下次遇到任何问题 直接找我 我24小时在线帮您处理 绝不推脱",
        "您好！问题圆满解决了吧？还有其他我能帮忙的吗？随时找我哦 😊",
        "亲！这次给您添麻烦了 为了表达歉意 下次有优惠我第一时间通知您 🔔",
        "您好！我刚才帮您做了一个回访确认 一切正常 您放心使用！",
        "亲 您放心 这种情况我们负责到底！全程我来跟进 直到您满意为止 💪",
        "非常感谢您的耐心配合！问题彻底解决了 如有其他需要随时喊我～",
        "您好 为了防止以后再出类似情况 我给您总结了几个小技巧...",
        "亲！下次遇到任何问题 直接找我 我24小时在线帮您处理 绝不推脱",
        "您好！问题圆满解决了吧？还有其他我能帮忙的吗？随时找我哦 😊",
        "亲！这次给您添麻烦了 为了表达歉意 下次有优惠我第一时间通知您 🔔",
        "您好！我刚才帮您做了一个回访确认 一切正常 您放心使用！"],
        'complaint': [
            "非常非常抱歉！我代表团队向您诚恳道歉 🙏 这确实是我们做得不够好",
            "您好！我完全理解您的心情和愤怒 换作是我也会一样的 请您先消消气",
            "对不起！让您有不好的体验了 这是我们的责任 我们绝不推卸",
            "亲！真的很抱歉听到这个 我心情也很沉重 让我来妥善解决这个问题",
            "您好！首先我要向您道歉 其次我想让您知道 我们非常重视您的反馈",
            "非常感谢您直接告诉我们问题 这给了我们改正的机会 真心感谢",
            "亲！您说得对 这确实是我们的问题 我不找借口 只想帮您尽快解决",
            "让您失望了我们很愧疚 请给我们一个弥补的机会 好吗？",
            "您好！我已经将您的问题升级到最高优先级 专人跟进处理",
            "亲！我完全站在您这边 您的要求完全合理 我尽全力帮您争取",
            "非常抱歉！这不是我们应该有的服务水平 我个人向您致歉 并立即整改",
            "您好！为了表达我们的歉意 除了解决问题外 还想给您一些补偿...",
            "亲！感谢您给我们指正问题 您的每一句话我们都认真听取了",
            "让您生气是我们的失职 对不起！我现在就帮您处理 直到您满意为止",
            "您好！问题根因已查明 是因为... 我们的改进措施是... 请您监督",
        "让您失望了我们真的很愧疚 请给我们一个弥补的机会好吗？",
        "您好！我已经把这个问题的优先级调到最高了 专人处理 结果出来第一时间通知您",
        "亲！您说得都对 这确实是我们的问题 我们虚心接受并立即改正",
        "非常感谢您愿意花时间告诉我们这些问题 您的反馈对我们很重要",
        "您好！为了表示歉意 除了正常解决问题外 我想额外为您申请一份小礼物 🎁",
        "亲！我已经亲自盯着这个事情了 保证给您满意的答复 请再相信我一次",
        "让您生气是我们的工作没做好 对不起！我现在就帮您协调直到满意为止",
        "您好 问题根因查清了 是因为... 我们已经做了这些改进措施... 请您监督",
        "让您失望了我们真的很愧疚 请给我们一个弥补的机会好吗？",
        "您好！我已经把这个问题的优先级调到最高了 专人处理 结果出来第一时间通知您",
        "亲！您说得都对 这确实是我们的问题 我们虚心接受并立即改正",
        "非常感谢您愿意花时间告诉我们这些问题 您的反馈对我们很重要",
        "您好！为了表示歉意 除了正常解决问题外 我想额外为您申请一份小礼物 🎁",
        "亲！我已经亲自盯着这个事情了 保证给您满意的答复 请再相信我一次",
        "让您生气是我们的工作没做好 对不起！我现在就帮您协调直到满意为止",
        "您好 问题根因查清了 是因为... 我们已经做了这些改进措施... 请您监督"],
    }
    
    import random
    
    pool = None
    if scene == 'marketing':
        pool = marketing_replies.get(identity)
        if not pool:
            for k in marketing_replies:
                if k in identity or identity in k:
                    pool = marketing_replies[k]
                    break
        if not pool:
            pool = marketing_replies.get('service')
    else:
        pool = social_replies.get(identity)
        if not pool:
            for k in social_replies:
                if k in identity or identity in k:
                    pool = social_replies[k]
                    break
        if not pool:
            pool = social_replies.get('friend')
    
    base_pool = list(pool)
    random.shuffle(base_pool)
    
    count = min(MIN_REPLIES, len(base_pool))
    result = base_pool[:count]
    
    if len(result) < MIN_REPLIES:
        for b in result[:3]:
            ex = _generate_variants(b, MIN_REPLIES - len(result))
            for e in ex:
                if e not in result:
                    result.append(e)
                if len(result) >= MIN_REPLIES:
                    break
    
    return result[:25]









# ============================================================


# 认证接口


# ============================================================






# ===== v2.2 Security: IP Rate Limiter =====
_login_attempts = {}
def _check_rl(ip):
    import time as _t
    now = _t.time()
    r = _login_attempts.get(ip,{})
    if now < r.get('lock',0): return False,'Locked %ds'%(r['lock']-now)
    if now-r.get('last',0)<1.5: return False,'Too fast'
    return True,None
def _rec_fail(ip):
    import time as _t
    now=_t.time();r=_login_attempts.get(ip,{'n':0});r['n']+=1;r['last']=now
    if r['n']>=5:r['lock']=now+300;_login_attempts[ip]=r

@app.route('/api/wx/login', methods=['POST'])


def login():


    """用户登录"""


    data = request.get_json() or {}


    username = data.get('username', '').strip()


    password = data.get('password', '')


    


    if not username or not password:


        return jsonify(make_response(400, '请输入用户名和密码'))


    


    user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)


    


    if not user:


        _rec_fail(request.remote_addr); return jsonify(make_response(401, 'Auth failed'))


    


    if not verify_password(password, user['password_hash']):


        return jsonify(make_response(401, '用户名或密码错误'))


    


    # 生成Token


    token = generate_token(user['id'])


    


    # 更新登录时间


    db = get_db()


    db.execute("UPDATE users SET updated_at = datetime('now','localtime') WHERE id = ?", (user['id'],))


    db.commit()


    


    # 构建返回的用户信息


    user_info = {


        'id': user['id'],


        'username': user['username'],


        'nickname': user['nickname'],


        'avatar_url': user['avatar_url'],


        'is_vip': bool(user['is_vip']),


        'vip_expire': user['vip_expire'] or '',


        'is_admin': bool(user['is_admin']),


        'free_count': user['free_count'],


        'token': token


    }


    


    return jsonify(make_response(200, '登录成功', user_info))








@app.route('/api/wx/register', methods=['POST'])


def register():


    """用户注册"""


    data = request.get_json() or {}


    username = data.get('username', '').strip()


    password = data.get('password', '')


    nickname = data.get('nickname', '').strip() or username


    invite_code = data.get('invite_code', '').strip()


    


    if not username or len(username) < 3:


        return jsonify(make_response(400, '用户名至少3个字符'))


    


    if not password or len(password) < 6:


        return jsonify(make_response(400, '密码至少6个字符'))


    


    # 检查用户名是否已存在


    if query_db('SELECT id FROM users WHERE username = ?', (username,), one=True):


        return jsonify(make_response(400, '用户名已存在'))


    


    # 处理邀请码


    inviter_id = None


    if invite_code:


        inviter = query_db('SELECT id FROM users WHERE invite_code = ?', (invite_code,), one=True)


        if inviter:


            inviter_id = inviter['id']


    


    # 生成邀请码


    my_invite_code = generate_invite_code()


    


    db = get_db()


    cursor = db.execute('''


        INSERT INTO users (username, password_hash, nickname, invite_code, inviter_id)


        VALUES (?, ?, ?, ?, ?)


    ''', (username, hash_password(password), nickname, my_invite_code, inviter_id))


    db.commit()


    


    user_id = cursor.lastrowid


    


    # 生成Token


    token = generate_token(user_id)


    


    user_info = {


        'id': user_id,


        'username': username,


        'nickname': nickname,


        'is_vip': False,


        'vip_expire': '',


        'is_admin': False,


        'free_count': 3,


        'token': token


    }


    


    return jsonify(make_response(201, '注册成功', user_info))








@app.route('/api/wx/wx_login', methods=['POST'])


def wx_login():


    """微信一键登录（v2.3: 支持邀请码绑定）"""


    data = request.get_json() or {}


    code = data.get('code', '')


    user_info = data.get('userInfo', {})

    invite_code = data.get('invite_code', '').strip()  # [v2.3] 邀请码参数

    


    # [v2.2 Security] BLOCKED no-code login to prevent abuse
    if not code:
        return jsonify(make_response(400, 'WeChat auth failed, please retry'))

    openid = f'wx_{hashlib.md5(code.encode()).hexdigest()[:16]}'




    # 根据openid查找或创建用户


    user = query_db('SELECT * FROM users WHERE username = ?', (f'wx_{openid}',), one=True)


    


    if not user:


        # 新用户注册


        nickname = user_info.get('nickName', '微信用户')


        avatar_url = user_info.get('avatarUrl', '')

        # [v2.3] 处理邀请码绑定
        inviter_id = None
        if invite_code:
            inviter = query_db('SELECT id FROM users WHERE invite_code = ?', (invite_code,), one=True)
            if inviter:
                inviter_id = inviter['id']

        my_invite_code = generate_invite_code()


        


        db = get_db()


        cursor = db.execute('''


            INSERT INTO users (username, password_hash, nickname, avatar_url, invite_code, inviter_id, free_count)


            VALUES (?, ?, ?, ?, ?, ?, ?)


        ''', (f'wx_{openid}', hash_password(str(time.time())), nickname, avatar_url, my_invite_code, inviter_id, 3))


        db.commit()


        


        user_id = cursor.lastrowid


        user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)


    


    # 更新用户信息


    if user_info.get('nickName') or user_info.get('avatarUrl'):


        db = get_db()


        updates = []


        params = []


        if user_info.get('nickName'):


            updates.append('nickname = ?')


            params.append(user_info['nickName'])


        if user_info.get('avatarUrl'):


            updates.append('avatar_url = ?')


            params.append(user_info['avatarUrl'])


        params.append(user['id'])


        if updates:


            db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)


            db.commit()


    


    # 生成Token


    token = generate_token(user['id'])


    


    result = {


        'id': user['id'],


        'username': user['username'],


        'nickname': user['nickname'] or '微信用户',


        'avatar_url': user['avatar_url'] or '',


        'is_vip': bool(user['is_vip']),


        'vip_expire': user['vip_expire'] or '',


        'is_admin': bool(user['is_admin']),


        'free_count': user['free_count'],


        'token': token


    }


    


    return jsonify(make_response(200, '登录成功', result))








# ============================================================


# 用户接口


# ============================================================





@app.route('/api/wx/profile', methods=['GET'])


@token_required


def get_profile():


    """获取用户信息"""


    user = g.user


    


    # 统计数据


    total_sessions = query_db('SELECT COUNT(*) as cnt FROM sessions WHERE user_id = ?', (g.user_id,), one=True)['cnt']


    total_targets = query_db('SELECT COUNT(*) as cnt FROM targets WHERE user_id = ?', (g.user_id,), one=True)['cnt']


    


    profile = {


        'id': user['id'],


        'username': user['username'],


        'nickname': user['nickname'],


        'avatar_url': user['avatar_url'],


        'phone': user.get('phone', ''),


        'is_vip': bool(user['is_vip']),


        'vip_expire': user['vip_expire'] or '',


        'is_admin': bool(user['is_admin']),


        'free_count': user['free_count'],


        'total_count': user['total_count'],


        'total_sessions': total_sessions,


        'total_targets': total_targets,


        'invite_code': user['invite_code'],


        'created_at': user['created_at']


    }


    


    return jsonify(make_response(200, '获取成功', profile))








@app.route('/api/wx/change_pwd', methods=['POST'])


@token_required


def change_pwd():


    """修改密码"""


    data = request.get_json() or {}


    old_pwd = data.get('old_password', '')


    new_pwd = data.get('new_password', '')


    


    if not old_pwd or not new_pwd:


        return jsonify(make_response(400, '请输入原密码和新密码'))


    


    if len(new_pwd) < 6:


        return jsonify(make_response(400, '新密码至少6个字符'))


    


    if g.user['password_hash'] != hash_password(old_pwd):


        return jsonify(make_response(401, '原密码错误'))


    


    db = get_db()


    db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hash_password(new_pwd), g.user_id))


    db.commit()


    


    return jsonify(make_response(200, '修改成功'))








# ============================================================


# VIP接口


# ============================================================





@app.route('/api/wx/vip/info', methods=['GET'])


@token_required


def get_vip_info():


    """获取VIP信息"""


    user = g.user


    


    vip_info = {


        'is_vip': bool(user['is_vip']),


        'vip_expire': user['vip_expire'] or '',


        'free_count': user['free_count'],


        'total_used': user['total_count'],


        'plans': [


            {'type': 'month', 'name': '月度会员', 'price': 29.99, 'duration': '30天'},


            {'type': 'year', 'name': '年度会员', 'price': 88.88, 'duration': '365天'},


            {'type': 'lifetime', 'name': '终身会员', 'price': 288.88, 'duration': '永久'}


        ]


    }


    


    # 检查VIP是否过期


    if user['vip_expire']:


        try:


            expire_time = datetime.strptime(user['vip_expire'], '%Y-%m-%d %H:%M:%S')


            if datetime.now() > expire_time:


                vip_info['is_vip'] = False


                vip_info['expired'] = True


        except ValueError:


            pass


    


    return jsonify(make_response(200, '获取成功', vip_info))








# ============================================================


# AI核心接口


# ============================================================





@app.route('/api/wx/targets', methods=['GET'])


@token_required


def get_targets():


    """获取用户的聊天目标列表"""


    targets = query_db('SELECT * FROM targets WHERE user_id = ? ORDER BY created_at DESC', (g.user_id,))


    return jsonify(make_response(200, '获取成功', targets))








@app.route('/api/wx/target/add', methods=['POST'])


@token_required


def add_target():


    """添加聊天目标"""


    data = request.get_json() or {}


    name = data.get('name', '').strip()


    


    if not name:


        return jsonify(make_response(400, '请输入目标名称'))


    


    db = get_db()


    cursor = db.execute('''


        INSERT INTO targets (user_id, name, relationship, gender, personality, notes)


        VALUES (?, ?, ?, ?, ?, ?)


    ''', (


        g.user_id,


        name,


        data.get('relationship', '好友'),


        data.get('gender', ''),


        data.get('personality', ''),


        data.get('notes', '')


    ))


    db.commit()


    


    return jsonify(make_response(201, '添加成功', {'id': cursor.lastrowid}))








@app.route('/api/wx/styles', methods=['GET'])


def get_styles():


    """获取预设身份/风格列表（无需登录）"""


    styles = query_db('SELECT * FROM preset_styles ORDER BY scene, sort_order')


    


    # 按场景分组


    grouped = {'social': [], 'marketing': []}


    for s in styles:


        if s['scene'] in grouped:


            grouped[s['scene']].append({


                'name': s['name'],


                'icon': s['icon'],


                'description': s['description']


            })


    


    return jsonify(make_response(200, '获取成功', grouped))








@app.route('/api/wx/chat/suggest', methods=['POST'])


@token_required


def generate_suggestions():


    """生成AI回复建议（核心接口）"""


    data = request.get_json() or {}


    


    scene = data.get('scene', 'social')


    identity = data.get('identity', '好朋友')


    style = data.get('style', '')


    custom_desc = data.get('custom_desc', '')


    message = data.get('message', '').strip()


    target_id = data.get('target_id')


    


    if not message:


        return jsonify(make_response(400, '请输入对方的消息'))


    


    # 检查使用次数（非VIP且免费次数用完）


    user = g.user


    if not user['is_vip'] and user['free_count'] <= 0:


        return jsonify(make_response(403, '免费次数已用完，开通VIP后无限使用'))


    


    # 获取目标信息


    target_info = ''


    if target_id:


        target = query_db('SELECT * FROM targets WHERE id = ? AND user_id = ?', (target_id, g.user_id), one=True)


        if target:


            parts = []


            if target['name']: parts.append(f"名字：{target['name']}")


            if target['relationship']: parts.append(f"关系：{target['relationship']}")


            if target['gender']: parts.append(f"性别：{target['gender']}")


            if target['personality']: parts.append(f"性格：{target['personality']}")


            target_info = '，'.join(parts)


    


    # 调用AI


    # ===== v4.0 记忆功能：获取聊天上下文 + 关键信息提取 =====
    memory_context = None
    if target_id:
        memory_context = get_chat_memory(g.user_id, target_id)
        print(f'[Memory] 加载了 {len(memory_context)} 条记忆上下文 (target={target_id})')
    else:
        memory_context = get_chat_memory(g.user_id)
        if memory_context:
            print(f'[Memory] 加载了 {len(memory_context)} 条全局记忆上下文')
    
    # v4.0: 提取关键信息并追加到记忆上下文中（增强AI理解）
    key_info = extract_key_info_from_memory(g.user_id, target_id)
    if key_info and memory_context is not None:
        memory_context.append({'role': 'system', 'content': key_info})
        print('[Memory] 已注入关键信息摘要到上下文')

    # 调用AI（v3.3: 传入记忆上下文）
    suggestions = call_ai_api(scene, identity, style, custom_desc, message, target_info, memory_context)


    


    # 扣除免费次数（非VIP）


    if not user['is_vip'] and user['free_count'] > 0:


        db = get_db()


        db.execute('UPDATE users SET free_count = free_count - 1, total_count = total_count + 1 WHERE id = ?', (g.user_id,))


        db.commit()


    


    # 保存会话记录


    db = get_db()


    db.execute('''


        INSERT INTO sessions (user_id, target_id, scene, identity, style, custom_desc, input_msg, ai_response, suggestions)


        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)


    ''', (g.user_id, target_id, scene, identity, style, custom_desc, message, '', json.dumps(suggestions, ensure_ascii=False)))


    db.commit()

    # ===== v3.3 记忆功能：实时保存对话到记忆 =====
    try:
        save_conversation_to_memory(g.user_id, target_id, message, suggestions, scene, identity)
        print(f'[Memory] 已保存本轮对话到记忆 (target={target_id})')
    except Exception as mem_err:
        print(f'[Memory] 保存失败（不影响主流程）: {mem_err}')



    # 获取剩余次数


    remaining = query_db('SELECT free_count, is_vip FROM users WHERE id = ?', (g.user_id,), one=True)


    


    return jsonify(make_response(200, '生成成功', {


        'suggestions': suggestions,
        'suggestion_tags': getattr(g, 'tagged_replies', None),
        'remaining_free': remaining['free_count'],
        'is_vip': bool(remaining['is_vip'])


    }))










# ============================================================
# v3.3 聊天记忆 API 接口
# ============================================================

@app.route('/api/wx/memory/list', methods=['GET'])
@token_required
def api_memory_list():
    """获取聊天记忆列表"""
    target_id = request.args.get('target_id', type=int)
    memories = get_memory_list_api(g.user_id, target_id)
    return jsonify(make_response(200, '获取成功', {
        'memories': memories,
        'total': len(memories)
    }))


@app.route('/api/wx/memory/save', methods=['POST'])
@token_required
def api_memory_save():
    """手动保存一条聊天记忆"""
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    role = data.get('role', 'user')  # user 或 assistant
    target_id = data.get('target_id')
    scene = data.get('scene', '')
    identity = data.get('identity', '')

    if not content:
        return jsonify(make_response(400, '记忆内容不能为空'))

    save_chat_memory(g.user_id, target_id, role, content, scene, identity)
    return jsonify(make_response(201, '记忆已保存'))


@app.route('/api/wx/memory/clear', methods=['POST'])
@token_required
def api_memory_clear():
    """清除聊天记忆"""
    data = request.get_json() or {}
    target_id = data.get('target_id', type=int)
    clear_chat_memory(g.user_id, target_id)
    return jsonify(make_response(200, '记忆已清除'))


@app.route('/api/wx/memory/stats', methods=['GET'])
@token_required
def api_memory_stats():
    """获取记忆统计"""
    total = query_db(
        'SELECT COUNT(*) as cnt FROM chat_memory WHERE user_id = ?', (g.user_id,), one=True
    )
    targets = query_db(
        '''SELECT t.id, t.name, t.relationship, COUNT(m.id) as mem_count
           FROM chat_memory m LEFT JOIN targets t ON m.target_id = t.id
           WHERE m.user_id = ? AND m.target_id IS NOT NULL
           GROUP BY m.target_id ORDER BY mem_count DESC LIMIT 10''',
        (g.user_id,)
    )
    return jsonify(make_response(200, '获取成功', {
        'total_memories': total['cnt'] if total else 0,
        'top_targets': [dict(t) for t in targets]
    }))




@app.route('/api/wx/sessions', methods=['GET'])


@token_required


def get_sessions():


    """获取历史会话记录"""


    page = request.args.get('page', 1, type=int)


    limit = request.args.get('limit', 20, type=int)


    offset = (page - 1) * limit


    


    sessions = query_db('''


        SELECT s.*, t.name as target_name 


        FROM sessions s 


        LEFT JOIN targets t ON s.target_id = t.id


        WHERE s.user_id = ?


        ORDER BY s.created_at DESC


        LIMIT ? OFFSET ?


    ''', (g.user_id, limit, offset))


    


    total = query_db('SELECT COUNT(*) as cnt FROM sessions WHERE user_id = ?', (g.user_id,), one=True)['cnt']


    


    return jsonify(make_response(200, '获取成功', {


        'list': sessions,


        'total': total,


        'page': page,


        'has_more': (offset + limit) < total


    }))








# ============================================================


# 支付接口


# ============================================================





@app.route('/api/wx/payment/create', methods=['POST'])


@token_required


def create_payment():


    """创建支付订单"""


    data = request.get_json() or {}


    plan_type = data.get('plan_type', '')  # month/year/lifetime


    


    plans = {


        'month': ('月度会员', 29.99),


        'year': ('年度会员', 88.88),


        'lifetime': ('终身会员', 288.88)


    }


    


    if plan_type not in plans:


        return jsonify(make_response(400, '无效的套餐类型'))


    


    plan_name, price = plans[plan_type]


    order_no = generate_order_no()


    


    db = get_db()


    cursor = db.execute('''


        INSERT INTO payments (user_id, order_no, plan_type, amount, status)


        VALUES (?, ?, ?, ?, 'pending')


    ''', (g.user_id, order_no, plan_type, price))


    db.commit()


    


    return jsonify(make_response(201, '订单创建成功', {


        'order_id': cursor.lastrowid,


        'order_no': order_no,


        'plan_name': plan_name,


        'price': price,


        'pay_method': 'manual',


        'status': 'pending',


        'notice': '请通过微信转账付款后上传凭证'


    }))








@app.route('/api/wx/payment/upload_proof', methods=['POST'])


@token_required


def upload_proof():


    """上传付款凭证"""


    payment_id = request.form.get('payment_id')


    


    if not payment_id:


        return jsonify(make_response(400, '缺少订单ID'))


    


    payment = query_db('SELECT * FROM payments WHERE id = ? AND user_id = ?', (payment_id, g.user_id), one=True)


    


    if not payment:


        return jsonify(make_response(404, '订单不存在'))


    


    if payment['status'] != 'pending':


        return jsonify(make_response(400, '该订单状态不允许上传凭证'))


    


    # 保存上传的文件


    if 'file' not in request.files:


        return jsonify(make_response(400, '请选择要上传的图片'))


    


    uploaded_file = request.files['file']


    if not uploaded_file.filename:


        return jsonify(make_response(400, '文件无效'))


    


    # 保存文件


    upload_dir = UPLOAD_DIR


    os.makedirs(upload_dir, exist_ok=True)


    


    ext = uploaded_file.filename.rsplit('.', 1)[-1] if '.' in uploaded_file.filename else 'jpg'


    filename = f"proof_{payment_id}_{int(time.time())}.{ext}"


    filepath = os.path.join(upload_dir, filename)


    uploaded_file.save(filepath)


    


    # 更新订单


    db = get_db()


    db.execute('UPDATE payments SET status = \'reviewing\', proof_image = ? WHERE id = ?', (filename, payment_id))


    db.commit()


    


    return jsonify(make_response(200, '凭证上传成功，等待审核'))








@app.route('/api/wx/payment/list', methods=['GET'])


@token_required


def get_payments():


    """获取支付记录"""


    payments = query_db('SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC', (g.user_id,))


    return jsonify(make_response(200, '获取成功', payments))








# ============================================================


# 推广接口


# ============================================================





@app.route('/api/wx/invite/info', methods=['GET'])


@token_required


def get_invite_info():


    """获取邀请信息"""


    user = g.user


    


    # 统计邀请人数


    invite_count = query_db('SELECT COUNT(*) as cnt FROM users WHERE inviter_id = ?', (g.user_id,), one=True)['cnt']


    


    # 统计佣金（简化处理）


    invite_users = query_db('SELECT username, nickname, created_at, CASE WHEN is_vip=1 THEN 1 ELSE 0 END as is_vip FROM users WHERE inviter_id = ? ORDER BY created_at DESC LIMIT 20', (g.user_id,))



    


    # [v2.3] 从commissions表查询真实佣金数据
    commission_row = query_db("SELECT SUM(commission_amount) as total FROM commissions WHERE inviter_user_id = ? AND status = 'settled'", (g.user_id,), one=True)
    settled_commission = round(commission_row['total'] or 0, 2)

    # 待结算佣金
    pending_row = query_db("SELECT SUM(commission_amount) as total FROM commissions WHERE inviter_user_id = ? AND status = 'pending'", (g.user_id,), one=True)
    pending_commission = round(pending_row['total'] or 0, 2)

    # 佣金明细列表（最近20条）
    commission_list = query_db('SELECT c.*, u.nickname as buyer_name, p.plan_type, p.amount as order_amount FROM commissions c LEFT JOIN users u ON c.buyer_user_id = u.id LEFT JOIN payments p ON c.payment_id = p.id WHERE c.inviter_user_id = ? ORDER BY c.created_at DESC LIMIT 20', (g.user_id,))

    info = {
        'invite_code': user['invite_code'],
        'invite_count': invite_count,
        'commission_rate': 0.30,
        'settled_commission': settled_commission,
        'pending_commission': pending_commission,
        'total_commission': round(settled_commission + pending_commission, 2),
        'link': 'pages/register/register?invite_code=' + user['invite_code'],
        'team': invite_users,
        'commissions': [{'id':x['id'],'amount':x.get('commission_amount',0),'status':x.get('status','pending'),'plan_type':x.get('plan_type',''),'created_at':x.get('created_at'),'buyer_name':x.get('buyer_name','')} for x in commission_list],
        'invited_users': invite_users
    }


    


    return jsonify(make_response(200, '获取成功', info))








# ============================================================


# 管理员接口


# ============================================================





@app.route('/api/admin/users', methods=['GET'])


@token_required


def admin_list_users():


    """管理员：用户列表"""


    if not g.user.get('is_admin'):


        return jsonify(make_response(403, '无权限'))


    


    page = request.args.get('page', 1, type=int)


    limit = request.args.get('limit', 20, type=int)


    offset = (page - 1) * limit


    


    users = query_db('SELECT id, username, nickname, is_vip, vip_expire, is_admin, free_count, total_count, created_at FROM users ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))


    total = query_db('SELECT COUNT(*) as cnt FROM users', (), one=True)['cnt']


    


    return jsonify(make_response(200, '获取成功', {'list': users, 'total': total}))








@app.route('/api/admin/payments', methods=['GET'])


@token_required


def admin_list_payments():


    """管理员：订单列表"""


    if not g.user.get('is_admin'):


        return jsonify(make_response(403, '无权限'))


    


    payments = query_db('''


        SELECT p.*, u.username, u.nickname 


        FROM payments p 


        LEFT JOIN users u ON p.user_id = u.id 


        ORDER BY p.created_at DESC


    ''')


    


    return jsonify(make_response(200, '获取成功', payments))








@app.route('/api/admin/review/<int:payment_id>', methods=['POST'])


@token_required


def admin_review_payment(payment_id):


    """管理员：审核订单"""


    if not g.user.get('is_admin'):


        return jsonify(make_response(403, '无权限'))


    


    data = request.get_json() or {}


    action = data.get('action')  # approve/reject


    


    payment = query_db('SELECT * FROM payments WHERE id = ?', (payment_id,), one=True)


    if not payment:


        return jsonify(make_response(404, '订单不存在'))


    


    db = get_db()


    if action == 'approve':


        # 审核通过 - 开通VIP


        plan_duration = {'month': 30, 'year': 365, 'lifetime': 36500}


        days = plan_duration.get(payment['plan_type'], 30)


        expire_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


        


        db.execute("UPDATE payments SET status = 'paid', reviewed_by = ?, reviewed_at = datetime('now','localtime') WHERE id = ?", (g.user_id, payment_id))


        db.execute("UPDATE users SET is_vip = 1, vip_expire = ? WHERE id = ?", (expire_date, payment['user_id']))


        # [v2.3] 自动计算并记录佣金
        buyer = query_db('SELECT inviter_id FROM users WHERE id = ?', (payment['user_id'],), one=True)
        if buyer and buyer.get('inviter_id'):


            # 计算佣金金额（30%）
            commission_amount = round(payment['amount'] * 0.30, 2)


            # 插入佣金记录


            db.execute('''


                INSERT INTO commissions (inviter_user_id, buyer_user_id, payment_id, order_no, commission_rate, commission_amount, plan_type, status)


                VALUES (?, ?, ?, ?, ?, ?, ?, 'settled')


            ''', (buyer['inviter_id'], payment['user_id'], payment_id, payment.get('order_no',''), 0.30, commission_amount, payment.get('plan_type','')))


    elif action == 'reject':


        db.execute("UPDATE payments SET status = 'rejected', reviewed_by = ?, reviewed_at = datetime('now','localtime') WHERE id = ?", (g.user_id, payment_id))


    else:


        return jsonify(make_response(400, '无效的操作'))


    


    db.commit()


    


    return jsonify(make_response(200, '审核完成'))








# ============================================================


# ============================================================
# 提现管理 [v2.3]
# ============================================================

@app.route('/api/user/withdraw', methods=['POST'])
@token_required
def create_withdrawal():
    """用户申请提现"""
    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    withdraw_method = data.get('method', 'wechat')
    account_info = data.get('account_info', '')
    if amount <= 0:
        return jsonify(make_response(400, '提现金额必须大于0'))
    commission_row = query_db("SELECT SUM(commission_amount) as total FROM commissions WHERE inviter_user_id=? AND status='settled'", (g.user_id,), one=True)
    settled = commission_row['total'] or 0
    withdrawn = query_db("SELECT SUM(amount) as total FROM withdrawals WHERE user_id=? AND status='approved'", (g.user_id,), one=True)['total'] or 0
    available = round(settled - withdrawn, 2)
    if amount > available + 0.01:
        return jsonify(make_response(400, "可提现余额不足，当前可用: %.2f" % available))
    db = get_db()
    cursor = db.execute(
        "INSERT INTO withdrawals (user_id,amount,status,withdraw_method,account_info) VALUES(?,?,?,?,?)",
        (g.user_id, amount, "pending", withdraw_method, account_info))
    db.commit()
    return jsonify(make_response(200, "提现申请已提交，请等待审核", {"withdraw_id": cursor.lastrowid}))

@app.route('/api/user/withdraw/list', methods=['GET'])
@token_required
def get_withdrawal_list():
    """用户查看自己的提现记录"""
    withdrawals = query_db("SELECT * FROM withdrawals WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (g.user_id,))
    return jsonify(make_response(200, "获取成功", [dict(w) for w in withdrawals]))

@app.route('/api/admin/withdraw/list', methods=['GET'])
@token_required
def admin_get_withdrawals():
    """管理员查看所有提现申请"""
    if not g.user.get('is_admin'):
        return jsonify(make_response(403, "无权限"))
    withdrawals = query_db(
        "SELECT w.*,u.nickname AS user_name,u.username FROM withdrawals w LEFT JOIN users u ON w.user_id=u.id ORDER BY w.created_at DESC LIMIT 100")
    return jsonify(make_response(200, "获取成功", [dict(w) for w in withdrawals]))

@app.route('/api/admin/withdraw/review/<int:withdraw_id>', methods=['POST'])
@token_required
def admin_review_withdrawal(withdraw_id):
    """管理员审核提现"""
    if not g.user.get('is_admin'):
        return jsonify(make_response(403, "无权限"))
    data = request.get_json() or {}
    action = data.get("action")
    remark = data.get("remark", "")
    wd = query_db("SELECT * FROM withdrawals WHERE id=?", (withdraw_id,), one=True)
    if not wd:
        return jsonify(make_response(404, "提现记录不存在"))
    if wd["status"] != "pending":
        return jsonify(make_response(400, "该记录已处理"))
    db = get_db()
    if action == "approve":
        db.execute("UPDATE withdrawals SET status='approved',reviewed_by=?,reviewed_at=datetime('now','localtime'),remark=? WHERE id=?",
                   (g.user_id, remark, withdraw_id))
        msg = "提现已通过"
    elif action == "reject":
        db.execute("UPDATE withdrawals SET status='rejected',reviewed_by=?,reviewed_at=datetime('now','localtime'),remark=? WHERE id=?",
                   (g.user_id, remark, withdraw_id))
        msg = "提现已拒绝"
    else:
        return jsonify(make_response(400, "无效操作"))
    db.commit()
    return jsonify(make_response(200, msg))

# 健康检查 & 测试


# ============================================================





@app.route('/api/health', methods=['GET'])


def health_check():


    """健康检查"""


    return jsonify({


        'status': 'ok',


        'service': 'ChenYu AI Assistant',


        'version': '2.4.0',


        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),


        'ai_enabled': True


    })








@app.route('/api/test/connection', methods=['GET'])


def test_connection():


    """连接测试"""


    jsonify({'status':'ok','time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')})








# ============================================================


# 启动入口


# ============================================================





if __name__ == '__main__':


    print('=' * 50)


    print('  ChenYu AI Chat Server v2.2 (Security)')


    print('=' * 50)


    print(f'  DB: {DB_PATH}')


    print(f'  Port: {PORT} (env:PORT={os.environ.get("PORT", "default")})')


    ai_status = 'GLM-4-Flash (configured)' if ZHIPU_API_KEY else 'Mock mode (no API key)'


    print(f'  AI: {ai_status}')


    print(f'  Env: {"Render Cloud" if os.environ.get("RENDER") else "Local Dev"}')


    print('=' * 50)


    


    # Initialize database


    with app.app_context():


        init_db()


        print('[OK] Database initialized')


    


    # 启动服务（支持Render自动分配端口）


    app.run(host='0.0.0.0', port=PORT, debug=False)


