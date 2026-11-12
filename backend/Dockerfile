FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 先拷贝运行所需源码，再安装本地项目依赖
# 只 COPY backend 与 algorithm，避免带入前端产物、文档与本地文件
ARG PIP_INDEX_URL=""
COPY algorithm /app/algorithm
COPY backend /app/backend
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} -e /app/algorithm -e /app/backend

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
