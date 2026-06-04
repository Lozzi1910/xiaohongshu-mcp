# 小红书 MCP Server

**让 AI 助手搜索、浏览、发布小红书笔记**

[![AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](pyproject.toml)

---

## ✨ 功能

| 功能 | MCP 工具 | 说明 |
|------|----------|------|
| 🔍 **搜索笔记** | `xhs_search(keyword, limit)` | 搜索小红书笔记，返回标题+链接 |
| 📖 **获取笔记** | `xhs_get_note(url)` | 查看笔记详情、正文、评论 |
| 📤 **发布笔记** | `xhs_publish(title, content, images)` | 发布图文笔记 |
| 🔑 **扫码登录** | `xhs_login_qrcode()` | 获取二维码，手机扫码登录 |
| ✅ **检查登录** | `xhs_check_login()` | 检查当前登录状态 |

## 🚀 快速开始

```bash
# 1. 安装
pip install -e .
playwright install chromium

# 2. 启动
python -m xiaohongshu_mcp.server

# 3. 配置到你的 MCP 客户端
```

### 扫码登录

```bash
# 启动后运行：
xhs_login_qrcode()  # 获取二维码 → 小红书 App 扫码
xhs_check_login()   # 确认已登录
```

## 🐳 Docker 部署

```bash
docker build -t xhs-mcp .
docker run -d -p 6789:6789 -v $HOME/.xiaohongshu_mcp:/data xhs-mcp
```

## 💰 定价

| 版本 | 价格 | 适用 |
|------|------|------|
| 🌟 个人版 | 免费 (AGPL-3.0) | 个人开发者 |
| 💼 商业版 | ¥499 | 单项目商用 |
| 🏢 企业版 | ¥2999 | 无限项目 + 优先支持 |

## 📦 项目结构

```
xiaohongshu-mcp/
├── xiaohongshu_mcp/
│   ├── __init__.py
│   ├── server.py      # FastMCP 入口 + 工具定义
│   └── core.py        # Playwright 控制器
├── data/              # 存储目录（cookies、二维码）
├── pyproject.toml
└── README.md
```

## 🔗 相关项目

- [Douyin-mcp](https://github.com/Lozzi1910/Douyin-mcp) — 抖音私信 MCP
- [WeChat-mcp](https://github.com/Lozzi1910/WeChat-mcp) — 微信消息 MCP

## ⭐ Star 支持

如果这个项目对你有帮助，欢迎 Star 支持！
