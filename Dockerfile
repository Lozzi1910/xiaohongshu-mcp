# 小红书 MCP Server — Docker
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（Playwright 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml README.md ./
COPY xiaohongshu_mcp/ ./xiaohongshu_mcp/
RUN pip install --no-cache-dir -e .

# 安装 Playwright Chromium
RUN python -m playwright install chromium

# 数据目录
VOLUME ["/data"]

# SSE 模式（默认端口 6789）
EXPOSE 6789
ENV XHS_HEADLESS=true

CMD ["python", "-m", "xiaohongshu_mcp.server", "--transport", "sse", "--port", "6789"]
