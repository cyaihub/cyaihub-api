# 🚀 沉鱼AI畅聊助手 - Zeabur 部署指南

> 一键将后端部署到云端，小程序即可访问线上API

---

## 前置条件

- ✅ 一个 [Zeabur](https://zeabur.com) 账号（免费额度够用）
- ✅ 智谱AI API Key（从 https://open.bigmodel.cn 获取）
- ✅ 代码托管在 **GitHub** 或 **Gitee**

---

## 方式一：Git仓库自动部署（推荐 ⭐）

### 第一步：推送代码到 Git

```bash
# 确保server/目录下有以下文件：
# ✅ app.py          — Flask主程序
# ✅ requirements.txt — Python依赖
# ✅ Dockerfile      — 容器构建配置（Zeabur可选）

git add server/
git commit -m "feat: v3.3 - Zeabur云部署支持"
git push origin main
```

### 第二步：Zeabur 控制台操作

1. 登录 [Zeabur Dashboard](https://dash.zeabur.com)
2. 点击 **「+ 创建项目」**
3. 选择 **「Deploy Service」→「Git」**
4. 授权你的 GitHub / Gitee 仓库
5. 选择 `沉鱼AI畅聊助手` 项目
6. 设置 **Root Directory** 为 `server/`
7. 点击 **「Deploy」** → 自动开始构建！

### 第三步：配置环境变量（关键！⚠️）

项目部署成功后，进入 Service → **Variables**，添加以下变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `ZHIPU_API_KEY` | 你的智谱API Key | ⚠️ **必填** |
| `ZHIPU_API_URL` | `https://open.bigmodel.cn/api/paas/v4` | 默认值 |
| `JWT_SECRET` | 随机64位字符串 | Token签名密钥 |
| `SECRET_KEY` | 随机48位字符串 | Flask加密密钥 |

> 💡 **生成随机密钥**：可以用这个命令生成
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

### 第四步：配置持久化存储（数据库）

Zeabur 默认文件系统是临时的（重启丢失），SQLite 数据库需要持久化：

1. 进入 Service → **Storage** (存储卷)
2. 点击 **「Add Volume」**
3. **挂载路径** 填写: `/app/data`
4. 这确保 `app.db` 在重启后不丢失

### 第五步：获取公网地址

部署完成后，Zeabur 会分配一个公网地址：
```
https://your-app-name.zeabur.app
```
把这个地址填入小程序的 `utils/api.js` 的 `BASE_URL` 即可。

---

## 方式二：Docker镜像部署

如果你不想用Git，可以直接构建Docker镜像推送：

### 构建并推送

```bash
cd server/

# 构建镜像
docker build -t chenyu-api:v3.2 .

# 推送到 Docker Hub
docker tag chenyu-api:v3.2 yourusername/chenyu-api:v3.2
docker push yourusername/chenyu-api:v3.2
```

### Zeabur 导入镜像

1. Dashboard → **Deploy Service** → **Docker Image**
2. 输入: `yourusername/chenyu-api:v3.2`
3. 同样需要配置环境变量和存储卷（同上第三、四步）

---

## 方式三：Zeabur CLI 部署

```bash
# 安装 CLI
npm install -g @zeabur/cli

# 登录
zeabur login

# 部署
cd server/
zeabur deploy --prebuilt
```

---

## 部署完成后检查清单

| 步骤 | 操作 | 状态 |
|------|------|------|
| 1 | 服务正常启动 | 访问 `/api/health` 返回 `{"status":"ok"}` |
| 2 | AI引擎可用 | 测试 `/api/wx/chat/suggest` 能返回AI回复 |
| 3 | 小程序连接 | `api.js` 中 BASE_URL 改为 Zeabur 地址 |
| 4 | 域名绑定（可选） | Settings → Domains 绑定 cyaihub.top |

---

## 小程序端修改（部署后必做）

部署成功后，修改 `utils/api.js`：

```javascript
// 开发环境（本地测试）
// const BASE_URL = 'http://localhost:5678'

// 生产环境（Zeabur线上）← 改这里！
const BASE_URL = 'https://your-app-name.zeabur.app'
```

然后在微信开发者工具中 **重新编译上传**。

---

## 常见问题

### Q: 部署后数据丢失？
**A:** 必须添加 Storage Volume（存储卷），挂载路径设为 `/app/data`

### Q: AI回复报错？
**A:** 检查 `ZHIPU_API_KEY` 环境变量是否正确设置

### Q: 如何查看日志？
**A:** Zeabur Dashboard → Service → **Logs** 标签页

### Q: 免费额度够用吗？
**A:** Zeabur 免费版提供足够的小型项目资源。超出后会暂停，可升级或等下月重置

---

_编写日期: 2026-04-27 | 执行者: 龙虾🦞_
