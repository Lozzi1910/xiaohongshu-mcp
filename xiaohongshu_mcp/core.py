"""
小红书 Playwright 控制器 — 处理浏览器自动化、登录、搜索、浏览、发布
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger("xhs-mcp")

DATA_DIR = Path(os.path.expanduser("~/.xiaohongshu_mcp"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_FILE = DATA_DIR / "storage.json"
COOKIES_FILE = DATA_DIR / "cookies.json"
QR_FILE = DATA_DIR / "login_qrcode.png"


class XHSController:
    """小红书控制器 — 封装所有 Playwright 操作"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._creator_page: Optional[Page] = None

    # ── 浏览器管理 ──────────────────────────────────────────────────────

    async def _ensure_browser(self) -> Page:
        """确保浏览器已启动，返回主页 page"""
        if self._page is not None:
            return self._page

        p = await async_playwright().start()
        self._browser = await p.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 加载已保存的 cookies
        if COOKIES_FILE.exists():
            try:
                cookies = json.loads(COOKIES_FILE.read_text())
                await context.add_cookies(cookies)
                logger.info(f"已加载 {len(cookies)} 个 cookies")
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {e}")

        self._page = await context.new_page()

        # 注入反检测脚本
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        """)

        return self._page

    async def _save_cookies(self):
        """保存当前 cookies 到文件"""
        if self._page is None:
            return
        context = self._page.context
        cookies = await context.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        logger.info(f"已保存 {len(cookies)} 个 cookies")

    # ── 登录 ────────────────────────────────────────────────────────────

    async def login_qrcode(self) -> str:
        """获取登录二维码"""
        page = await self._ensure_browser()
        await page.goto("https://www.xiaohongshu.com", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 点击登录按钮
        try:
            login_btn = await page.query_selector('text=登录')
            if login_btn:
                await login_btn.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # 尝试找到二维码并截图
        await page.wait_for_timeout(3000)
        qr_selector = 'canvas[class*="qrcode"], img[class*="qrcode"], div[class*="qrcode"] img'
        try:
            qr_element = await page.wait_for_selector(qr_selector, timeout=10000)
            await qr_element.screenshot(path=str(QR_FILE))
            return f"二维码已保存到 {QR_FILE}，请用小红书 App 扫码登录"
        except Exception:
            # 尝试直接截图整个页面
            await page.screenshot(path=str(QR_FILE))
            return f"登录二维码页面已截图到 {QR_FILE}"

    async def check_login(self) -> str:
        """检查登录状态"""
        page = await self._ensure_browser()
        await page.goto("https://www.xiaohongshu.com", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 检查是否有用户头像（已登录标志）
        try:
            avatar = await page.query_selector('[class*="avatar"], [class*="user"], [class*="login"]')
            if avatar:
                text = await page.evaluate("document.body.innerText")
                if "登录" not in text[:500]:
                    await self._save_cookies()
                    return "已登录 ✅"
            # 检查 cookies
            cookies = await page.context.cookies()
            has_session = any(c["name"] in ("a1", "web_session") for c in cookies)
            if has_session:
                return "有登录 cookie，但页面状态不确定，建议重新登录"
            return "未登录 ❌"
        except Exception as e:
            return f"检查登录状态失败: {e}"

    # ── 搜索 ────────────────────────────────────────────────────────────

    async def search_notes(self, keyword: str, limit: int = 10) -> str:
        """搜索笔记"""
        page = await self._ensure_browser()
        encoded = keyword
        await page.goto(
            f"https://www.xiaohongshu.com/search_result?keyword={encoded}",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(3000)

        # 等待笔记列表加载
        try:
            await page.wait_for_selector(
                'section[class*="note"], div[class*="feeds"], div[class*="search-result"]',
                timeout=10000,
            )
        except Exception:
            pass

        await page.wait_for_timeout(2000)

        # 提取笔记信息
        results = await page.evaluate("""() => {
            const items = document.querySelectorAll('section[class*="note"], a[href*="explore"]');
            const notes = [];
            const limit = arguments[0] || 10;
            for (const item of items) {
                if (notes.length >= limit) break;
                const link = item.tagName === 'A' ? item : item.querySelector('a');
                const href = link ? link.getAttribute('href') : '';
                const title = item.querySelector('[class*="title"], [class*="note"]')?.textContent?.trim() || '';
                const likes = item.querySelector('[class*="like"], [class*="count"]')?.textContent?.trim() || '';
                if (href && title) {
                    notes.push({
                        url: href.startsWith('http') ? href : `https://www.xiaohongshu.com${href}`,
                        title: title.slice(0, 100),
                        likes: likes
                    });
                }
            }
            return JSON.stringify(notes);
        }""", limit)

        if not results or results == "[]":
            return f"搜索「{keyword}」未找到结果，可能需要登录"

        notes = json.loads(results)
        output = [f"🔍 搜索「{keyword}」共 {len(notes)} 条结果:\n"]
        for i, n in enumerate(notes, 1):
            output.append(f"{i}. {n['title']}")
            output.append(f"   {n['url']}")
            if n.get('likes'):
                output.append(f"   ❤️ {n['likes']}")
            output.append("")
        return "\n".join(output)

    # ── 获取笔记详情 ────────────────────────────────────────────────────

    async def get_note(self, url: str) -> str:
        """获取笔记详情和评论"""
        page = await self._ensure_browser()
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 提取笔记信息
        info = await page.evaluate("""() => {
            const title = document.querySelector('[class*="title"]')?.textContent?.trim() || '';
            const desc = document.querySelector('[class*="desc"], [class*="content"]')?.textContent?.trim() || '';
            const author = document.querySelector('[class*="author"], [class*="name"], [class*="username"]')?.textContent?.trim() || '';
            const likes = document.querySelector('[class*="like"] [class*="count"], [class*="like-wrapper"]')?.textContent?.trim() || '';
            const collects = document.querySelector('[class*="collect"] [class*="count"]')?.textContent?.trim() || '';
            const comments = [];
            document.querySelectorAll('[class*="comment-item"], [class*="reply"]').forEach(c => {
                const user = c.querySelector('[class*="username"]')?.textContent?.trim() || '';
                const text = c.querySelector('[class*="content"], [class*="text"]')?.textContent?.trim() || '';
                if (text) comments.push(`${user}: ${text}`);
            });
            return JSON.stringify({ title, desc: desc.slice(0, 500), author, likes, collects, comments: comments.slice(0, 20) });
        }""")

        if not info or info == "{}":
            return "无法获取笔记内容，页面可能未完全加载"

        data = json.loads(info)
        output = [f"📖 {data['title']}"]
        if data['author']:
            output.append(f"👤 {data['author']}")
        if data['likes'] or data['collects']:
            output.append(f"❤️ {data['likes']}  ⭐ {data['collects']}")
        output.append(f"\n{data['desc']}")
        if data['comments']:
            output.append(f"\n💬 评论 ({len(data['comments'])}条):")
            for c in data['comments'][:10]:
                output.append(f"  {c}")
        return "\n".join(output)

    # ── 发布笔记 ────────────────────────────────────────────────────────

    async def publish_note(self, title: str, content: str, images: list[str]) -> str:
        """发布图文笔记（需登录创作者平台）"""
        page = await self._ensure_browser()
        await page.goto("https://creator.xiaohongshu.com", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 检查是否登录
        page_text = await page.evaluate("document.body.innerText")
        if "登录" in page_text[:1000] and "发布" not in page_text[:2000]:
            return "未登录创作者平台，请先扫码登录"

        # 点击发布按钮
        try:
            publish_btn = await page.query_selector('text=发布, text=写笔记, [class*="publish"]')
            if publish_btn:
                await publish_btn.click()
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        await page.goto(
            "https://creator.xiaohongshu.com/publish/publish",
            wait_until="networkidle",
        )
        await page.wait_for_timeout(3000)

        return (
            f"发布页面已打开。请手动完成以下步骤：\n"
            f"1. 上传图片: {images}\n"
            f"2. 填写标题: {title}\n"
            f"3. 填写正文: {content[:200]}...\n"
            f"4. 点击发布\n\n"
            f"（小红书 web 发布涉及图片上传和富文本编辑器，\n"
            f" 完整自动化将在后续版本实现）"
        )

    # ── 资源清理 ──────────────────────────────────────────────────────

    async def close(self):
        if self._browser:
            await self._save_cookies()
            await self._browser.close()
            self._browser = None
            self._page = None
