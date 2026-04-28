# 沉鱼AI畅聊助手 - Dockerfile (Render/通用部署)
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录（用于SQLite持久化）
RUN mkdir -p /app/data

# 环境变量（可在Render Dashboard中覆盖）
ENV PORT=10000
ENV DB_PATH=/app/data/app.db

# 暴露端口
EXPOSE ${PORT}

# 使用Gunicorn启动（生产环境标准）
CMD gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --timeout 120
