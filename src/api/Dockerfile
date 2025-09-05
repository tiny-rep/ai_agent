FROM downloads.unstructured.io/unstructured-io/unstructured:0.13.7 AS base
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

COPY requirements.txt .

# 构建缓存并使用pip安装严格版本的requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

#二阶段构建
FROM base AS production

WORKDIR /app/api

# 设置用户为root
USER root

# 定义环境变量
ENV FLASK_APP=app/http/app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV NLTK_DATA=/app/api/internal/core/unstructured/nltk_data
ENV HF_ENDPOINT=https://hf-mirror.com

# 设置容器时区为中国时区
ENV TZ=Asia/Shanghai

# 复制源码
COPY . /app/api

ENV PATH="/home/notebook-user/.local/bin:${PATH}"

# 复制运行脚本并设置权限
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5001

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
