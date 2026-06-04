"""
小红书 Playwright 控制器 — 浏览器自动化、登录、搜索、浏览、互动、发布
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

logger = logging.getLogger("xhs-mcp")

DATA_DIR = Path(os.path.expanduser("~/.xiaohongshu_mcp"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
COOKIES_FILE = DATA_DIR / "cookies.json"
QR_FILE = DATA_DIR / "login_qrcode.png"

BASE_URL = "https://www.xiaohongshu.com"
CREATOR_URL = "https://creator.xiaohongshu.com"


def _extract_note_id(url: str) -> str:
    """从 URL 提取笔记 ID"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    parts = path.split("/")
    if "explore" in parts:
        idx = parts.index("explore") + 1
        if idx < len(parts):
            return parts[idx]
    return parts[-1] if parts else ""


class XHSController:
    """小红书控制器 — 封装所有 Playwright 操作"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._creator_page: Optional[Page] = None

    # ── 浏览器管理 ──────────────────────────────────────────────────────

    async def _ensure_browser(self) -> Page:
        if self._page is not None and self._context is not None:
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
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 加载 cookies
        if COOKIES_FILE.exists():
            try:
                cookies = json.loads(COOKIES_FILE.read_text())
                await self._context.add_cookies(cookies)
                logger.info(f"已加载 {len(cookies)} 个 cookies")
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {e}")

        self._page = await self._context.new_page()

        # 反检测脚本
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        """)
        return self._page

    async def _save_cookies(self):
        if self._context is None:
            return
        cookies = await self._context.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        logger.info(f"已保存 {len(cookies)} 个 cookies")

    async def _wait_loaded(self, page: Page, timeout: int = 8000):
        """等待页面加载完成"""
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass
        await page.wait_for_timeout(2000)

    # ── 登录 ────────────────────────────────────────────────────────────

    async def login_qrcode(self) -> str:
        """获取登录二维码"""
        page = await self._ensure_browser()
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await self._wait_loaded(page)

        # 等待二维码出现
        selectors = [
            'canvas[class*="qrcode"]',
            'img[class*="qrcode"]',
            'div[class*="qrcode"] img',
            '[class*="QRCode"] img',
        ]
        qr_found = False
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=5000)
                if el:
                    await el.screenshot(path=str(QR_FILE))
                    qr_found = True
                    break
            except Exception:
                continue

        if not qr_found:
            await page.screenshot(path=str(QR_FILE))

        return (
            f"📱 二维码已保存到 {QR_FILE}\n"
            f"请用小红书 App 扫描登录\n"
            f"登录后运行 xhs_check_login() 确认状态"
        )

    async def check_login(self) -> str:
        """检查登录状态"""
        page = await self._ensure_browser()
        await page.goto(f"{BASE_URL}/explore", wait_until="domcontentloaded")
        await self._wait_loaded(page, timeout=10000)

        # 检查页面是否包含用户信息
        body_text = await page.evaluate("document.body.innerText")

        # 检查特定登录标记
        try:
            has_notification = await page.query_selector('[class*="notification"]')
            has_avatar = await page.query_selector('[class*="avatar"]')
            if has_notification or has_avatar:
                await self._save_cookies()
                return "✅ 已登录"
        except Exception:
            pass

        # 检查 cookies
        if self._context:
            cookies = await self._context.cookies()
            has_session = any(
                c["name"] in ("a1", "web_session", "sessionid") and c.get("value")
                for c in cookies
            )
            if has_session:
                return "⚠️ 有登录 cookie 但页面状态不确定，可尝试重新登录"

        return "❌ 未登录"

    # ── 搜索 ────────────────────────────────────────────────────────────

    async def search_notes(self, keyword: str, limit: int = 10) -> str:
        """搜索笔记"""
        page = await self._ensure_browser()
        await page.goto(
            f"{BASE_URL}/search_result/{keyword}",
            wait_until="domcontentloaded",
        )
        await self._wait_loaded(page, timeout=15000)

        # 等待笔记列表出现
        feed_selectors = [
            'section[class*="note"]',
            'div[class*="feeds"]',
            'a[href*="explore"]',
            '[class*="search-result"] section',
        ]
        for sel in feed_selectors:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue

        await page.wait_for_timeout(2000)

        # 提取笔记信息 — 使用更健壮的提取方式
        results = await page.evaluate(f"""() => {{
            const items = document.querySelectorAll('a[href*="explore"], section[class*="note"]');
            const notes = [];
            const limit = {limit};

            for (const item of items) {{
                if (notes.length >= limit) break;
                const link = item.tagName === 'A' ? item : item.querySelector('a');
                const href = link ? link.getAttribute('href') : '';
                if (!href || !href.includes('explore')) continue;

                const title = item.querySelector('[class*="title"], [class*="note"]')
                    ?.textContent?.trim() || '';
                const likes = item.querySelector('[class*="like"], [class*="count"]')
                    ?.textContent?.trim() || '';
                const author = item.querySelector('[class*="author"], [class*="name"]')
                    ?.textContent?.trim() || '';

                notes.push({{
                    url: href.startsWith('http') ? href : '{BASE_URL}' + href.split('?')[0],
                    title: title.slice(0, 80),
                    likes: likes,
                    author: author
                }});
            }}
            return JSON.stringify(notes);
        }}""")

        if not results or results == "[]":
            return f"🔍 搜索「{keyword}」未找到结果"

        notes = json.loads(results)
        output = [f"🔍 搜索「{keyword}」— {len(notes)} 条结果:\n"]
        for i, n in enumerate(notes, 1):
            output.append(f"{i}. {n['title']}")
            if n.get("author"):
                output.append(f"   👤 {n['author']}")
            output.append(f"   🔗 {n['url']}")
            if n.get("likes"):
                output.append(f"   ❤️ {n['likes']}")
            output.append("")
        return "\n".join(output)

    # ── 获取笔记详情 ────────────────────────────────────────────────────

    async def get_note(self, url: str) -> str:
        """获取笔记详情和评论"""
        page = await self._ensure_browser()
        await page.goto(url, wait_until="domcontentloaded")
        await self._wait_loaded(page, timeout=15000)

        # 等待内容加载
        content_selectors = [
            '[class*="title"]',
            '[class*="content"]',
            '[class*="note"]',
        ]
        for sel in content_selectors:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue

        info = await page.evaluate("""() => {
            // 标题
            const titleEl = document.querySelector('[class*="title"]');
            const title = titleEl ? titleEl.textContent.trim() : '';

            // 正文
            const descEl = document.querySelector('[class*="desc"], [class*="content"], [class*="note-text"]');
            const desc = descEl ? descEl.textContent.trim().slice(0, 1000) : '';

            // 作者
            const authorEl = document.querySelector('[class*="author"] [class*="name"], [class*="username"], [class*="user-name"]');
            const author = authorEl ? authorEl.textContent.trim() : '';

            // 互动数据
            const getCount = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.textContent.trim() : '';
            };
            const likes = getCount('[class*="like"] [class*="count"], [class*="likes"] [class*="num"]');
            const collects = getCount('[class*="collect"] [class*="count"], [class*="favorite"] [class*="num"]');

            // 评论
            const comments = [];
            document.querySelectorAll('[class*="comment-item"], [class*="reply-item"]').forEach(c => {
                const user = c.querySelector('[class*="username"], [class*="name"]')?.textContent?.trim() || '';
                const text = c.querySelector('[class*="content"], [class*="text"]')?.textContent?.trim() || '';
                if (text) comments.push(`${user}: ${text.slice(0, 200)}`);
            });

            // 图片
            const images = [];
            document.querySelectorAll('[class*="carousel"] img, [class*="swiper"] img, [class*="slide"] img').forEach(img => {
                const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                if (src && !images.includes(src)) images.push(src);
            });

            return JSON.stringify({
                title: title.slice(0, 100),
                desc: desc.slice(0, 1000),
                author, likes, collects,
                comments: comments.slice(0, 20),
                images: images.slice(0, 9)
            });
        }""")

        if not info or info == "{}":
            return "无法获取笔记内容，页面可能未完全加载"

        data = json.loads(info)
        output = [f"📖 {data['title'] or '（无标题）'}"]
        if data.get("author"):
            output.append(f"👤 {data['author']}")
        if data.get("likes") or data.get("collects"):
            output.append(f"❤️ {data['likes'] or 0}  ⭐ {data['collects'] or 0}")
        if data.get("images"):
            output.append(f"🖼️ {len(data['images'])} 张图片")
        if data.get("desc"):
            output.append(f"\n{data['desc']}")
        if data.get("comments"):
            output.append(f"\n💬 评论 ({len(data['comments'])}条):")
            for c in data["comments"][:10]:
                output.append(f"  {c}")
        return "\n".join(output)

    # ── 发布笔记 ────────────────────────────────────────────────────────

    async def publish_note(self, title: str, content: str, images: list[str]) -> str:
        """发布图文笔记（需登录创作者平台）"""
        # 验证输入
        if len(title) > 20:
            return f"❌ 标题不能超过 20 字（当前 {len(title)} 字）"
        if len(content) > 1000:
            return f"❌ 正文不能超过 1000 字（当前 {len(content)} 字）"

        page = await self._ensure_browser()

        # 打开创作者平台
        await page.goto(f"{CREATOR_URL}/publish/publish", wait_until="domcontentloaded")
        await self._wait_loaded(page, timeout=15000)

        # 检查是否登录
        page_text = await page.evaluate("document.body.innerText")
        if "登录" in page_text[:500]:
            return "❌ 未登录创作者平台，请先运行 xhs_login_qrcode() 扫码登录"

        result_lines = [
            f"📤 准备发布笔记:\n",
            f"标题: {title}\n",
            f"正文: {content[:200]}{'...' if len(content) > 200 else ''}\n",
            f"图片: {len(images)} 张\n",
        ]

        # 尝试上传第一张图片
        if images:
            try:
                file_input = await page.query_selector(
                    'input[type="file"], [class*="upload"] input[type="file"]'
                )
                if file_input:
                    first_img = images[0]
                    if os.path.exists(first_img):
                        await file_input.set_input_files(first_img)
                        await page.wait_for_timeout(3000)
                        result_lines.append("✅ 首张图片已上传\n")
                    else:
                        result_lines.append(f"⚠️ 图片不存在: {first_img}\n")
                else:
                    result_lines.append("⚠️ 未找到上传控件\n")
            except Exception as e:
                result_lines.append(f"⚠️ 图片上传失败: {e}\n")

        # 填写标题
        try:
            title_input = await page.query_selector(
                '[class*="title"] input, [class*="title"] [contenteditable], '
                '[placeholder*="标题"], [placeholder*="title"]'
            )
            if title_input:
                await title_input.click()
                await title_input.fill(title)
                result_lines.append("✅ 标题已填写\n")
        except Exception as e:
            result_lines.append(f"⚠️ 标题填写失败: {e}\n")

        # 填写正文
        try:
            content_area = await page.query_selector(
                '[class*="content"] [contenteditable], '
                '[class*="editor"] [contenteditable], '
                '[placeholder*="正文"], [placeholder*="写"]'
            )
            if content_area:
                await content_area.click()
                await content_area.fill(content)
                result_lines.append("✅ 正文已填写\n")
        except Exception as e:
            result_lines.append(f"⚠️ 正文填写失败: {e}\n")

        result_lines.append(
            f"\n📌 请手动检查页面并点击「发布」按钮\n"
            f"（小红书 web 发布涉及复杂表单校验，自动发布将在后续版本完善）"
        )
        return "\n".join(result_lines)

    # ── 互动工具 ────────────────────────────────────────────────────────

    async def like_note(self, url: str) -> str:
        """点赞笔记"""
        page = await self._ensure_browser()
        await page.goto(url, wait_until="domcontentloaded")
        await self._wait_loaded(page)

        try:
            like_btn = await page.query_selector(
                '[class*="like"]:not([class*="count"]):not([class*="num"]), '
                '[class*="like-btn"], [d*="like"]'
            )
            if like_btn:
                await like_btn.click()
                await page.wait_for_timeout(1000)
                return "✅ 点赞成功"
            return "⚠️ 未找到点赞按钮"
        except Exception as e:
            return f"❌ 点赞失败: {e}"

    async def comment_note(self, url: str, text: str) -> str:
        """评论笔记"""
        page = await self._ensure_browser()
        await page.goto(url, wait_until="domcontentloaded")
        await self._wait_loaded(page)

        try:
            comment_input = await page.query_selector(
                '[class*="comment"] [contenteditable], '
                '[placeholder*="评论"], [placeholder*="说"], '
                '[class*="input"] [contenteditable]'
            )
            if comment_input:
                await comment_input.click()
                await comment_input.fill(text)
                await page.wait_for_timeout(500)

                submit_btn = await page.query_selector(
                    '[class*="submit"], [class*="send"], '
                    'button:has-text("发布"), button:has-text("发送")'
                )
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(1000)
                    return "✅ 评论成功"
                return "⚠️ 已填写评论，请手动点击发送"
            return "⚠️ 未找到评论输入框"
        except Exception as e:
            return f"❌ 评论失败: {e}"

    # ── 用户信息 ────────────────────────────────────────────────────────

    async def user_profile(self, user_id: str) -> str:
        """获取用户主页信息"""
        page = await self._ensure_browser()
        await page.goto(
            f"{BASE_URL}/user/profile/{user_id}",
            wait_until="domcontentloaded",
        )
        await self._wait_loaded(page)

        info = await page.evaluate("""() => {
            const name = document.querySelector('[class*="name"], [class*="username"]')
                ?.textContent?.trim() || '';
            const desc = document.querySelector('[class*="desc"], [class*="bio"]')
                ?.textContent?.trim() || '';
            const counts = document.querySelectorAll('[class*="count"], [class*="num"]');
            const data = {};
            counts.forEach((c, i) => {
                data[`count_${i}`] = c.textContent.trim();
            });
            return JSON.stringify({name, desc, ...data});
        }""")

        if not info or info == "{}":
            return "无法获取用户信息"
        data = json.loads(info)
        return (
            f"👤 {data.get('name', user_id)}\n"
            f"{data.get('desc', '')}"
        )

    # ── 资源清理 ──────────────────────────────────────────────────────

    async def close(self):
        if self._browser:
            await self._save_cookies()
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            self._creator_page = None
