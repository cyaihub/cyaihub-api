# 沉鱼AI畅聊助手 - Dockerfile (Zeabur/通用部署)
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

# 环境变量（可在Zeabur Dashboard中覆盖）
ENV PORT=5678
ENV DB_PATH=/app/data/app.db

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/api/health')" || exit 1

# 暴露端口
EXPOSE ${PORT}

# 启动命令（Zeabur会自动用Gunicorn包装）
CMD ["python", "app.py"]
