# 小红书也有 MCP Server 了！让任何 AI 都能搜索、浏览、发布小红书笔记

> 继抖音私信 MCP 之后，我们又做了一个——小红书 MCP Server。搜索、看笔记、点赞、评论、发布，AI 能做的事又多了一件。

---

## 为什么是小红书？

3 亿月活，国内最强势的种草平台。每天有海量的内容在被创造和消费，但内容管理工具极度匮乏。

如果你想：
- 搜索某个关键词的最新笔记
- 分析竞品的内容策略
- 定时发布内容
- 批量管理互动

——目前没有一个好用的 API。直到现在。

## 我们做了什么：小红书 MCP Server

**项目地址：** https://github.com/Lozzi1910/xiaohongshu-mcp

这是一个基于 Playwright 的 MCP Server，通过浏览器自动化操控小红书网页版，暴露为标准 MCP 工具给 AI 助手调用。

### 8 个 MCP 工具

| 功能 | MCP 工具 | 说明 |
|------|----------|------|
| 🔑 扫码登录 | `xhs_login_qrcode()` | 获取二维码，App 扫码 |
| ✅ 检查登录 | `xhs_check_login()` | 确认登录状态 |
| 🔍 搜索笔记 | `xhs_search(keyword, limit)` | 搜索笔记，返回标题+链接+作者 |
| 📖 获取笔记 | `xhs_get_note(url)` | 笔记详情、正文、评论、图片 |
| 📤 发布笔记 | `xhs_publish(title, content, images)` | 图文笔记发布 |
| ❤️ 点赞 | `xhs_like(url)` | 点赞/取消点赞 |
| 💬 评论 | `xhs_comment(url, text)` | 发表评论 |
| 👤 用户信息 | `xhs_user_profile(user_id)` | 获取用户主页 |

### 技术架构

```
MCP Client → xhs-mcp-server → Playwright → 小红书网页版
```

- Playwright 浏览器自动化，自动处理登录态和反爬
- Cookie 持久化，一次登录长期使用
- Docker 一键部署
- 与 Douyin-mcp、WeChat-mcp 同一技术栈

### 快速上手

```bash
# 安装
pip install xhs-mcp-server
playwright install chromium

# 启动
python -m xiaohongshu_mcp.server

# 扫码登录
xhs_login_qrcode() → 小红书 App 扫码
xhs_check_login() → 确认登录

# 开始使用
xhs_search("北京探店")
xhs_get_note("笔记链接")
```

也支持 Docker：

```bash
docker compose up -d
```

### 应用场景

**市场调研**
AI 自动搜索竞品笔记，分析内容策略和用户反馈。

**内容运营**
批量定时发布笔记，自动回复评论。

**KOL 监测**
追踪特定作者的内容更新和互动数据。

**趋势分析**
监控关键词的热度变化，捕捉热门话题。

### 定价

| 版本 | 价格 | 适用 |
|------|------|------|
| 个人版 | 免费 (AGPL-3.0) | 个人开发者 |
| 商业版 | ¥499 | 单项目商用 |
| 企业版 | ¥2999 | 无限项目 + 优先支持 |

### 与竞品对比

市面上已有几个小红书 MCP 项目：

- **xpzouying/xiaohongshu-mcp** (Go, 13.9k⭐) — 功能最全
- **ShunL12324/xhs-mcp** (TypeScript, ~2k⭐)

我们的优势在于：
1. **Python 技术栈** — 与 Douyin-mcp / WeChat-mcp 同一体系，易扩展
2. **简单直观** — 8 个工具覆盖核心需求，不复杂
3. **持续迭代** — 已有两个 MCP 项目的维护经验

### 相关项目

- [Douyin-mcp](https://github.com/Lozzi1910/Douyin-mcp) — 抖音私信 MCP
- [WeChat-mcp](https://github.com/Lozzi1910/WeChat-mcp) — 微信消息 MCP

---

**项目地址：** https://github.com/Lozzi1910/xiaohongshu-mcp

如果项目对你有帮助，欢迎 ⭐ Star 支持！

*本文由 AI 辅助撰写，项目作者 Lozzi 出品。*
