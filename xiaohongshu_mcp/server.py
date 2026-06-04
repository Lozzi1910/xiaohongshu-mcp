"""
小红书 MCP Server — 将小红书搜索/浏览/发布功能暴露为 MCP 工具

使用方式:
    python -m xiaohongshu_mcp.server                      # stdio 模式 (默认)
    python -m xiaohongshu_mcp.server --transport sse --port 6789  # SSE 模式 (Docker)

暴露的 MCP 工具:
    1. xhs_login_qrcode()        — 获取登录二维码
    2. xhs_check_login()         — 检查登录状态
    3. xhs_search(keyword, limit) — 搜索小红书笔记
    4. xhs_get_note(url)         — 获取笔记详情和评论
    5. xhs_publish(title, content, images) — 发布图文笔记
    6. xhs_like(url)             — 点赞/取消点赞笔记
    7. xhs_comment(url, text)    — 评论笔记
    8. xhs_user_profile(user_id) — 获取用户主页信息
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Optional

from mcp.server import FastMCP

from xiaohongshu_mcp.core import XHSController

# ── logger ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("xhs-mcp")


# ── controller singleton ────────────────────────────────────────────────

_ctrl: Optional[XHSController] = None


def _get_ctrl() -> XHSController:
    global _ctrl
    if _ctrl is None:
        headless = os.environ.get("XHS_HEADLESS", "").lower() in ("true", "1", "yes")
        _ctrl = XHSController(headless=headless)
    return _ctrl


# ── MCP 工具 ────────────────────────────────────────────────────────────

mcp = FastMCP("xhs-mcp-server")


@mcp.tool()
async def xhs_login_qrcode() -> str:
    """获取小红书登录二维码（扫码登录）"""
    ctrl = _get_ctrl()
    return await ctrl.login_qrcode()


@mcp.tool()
async def xhs_check_login() -> str:
    """检查当前小红书登录状态"""
    ctrl = _get_ctrl()
    return await ctrl.check_login()


@mcp.tool()
async def xhs_search(keyword: str, limit: int = 10) -> str:
    """搜索小红书笔记

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量（默认10，最大30）
    """
    ctrl = _get_ctrl()
    return await ctrl.search_notes(keyword, min(limit, 30))


@mcp.tool()
async def xhs_get_note(url: str) -> str:
    """获取小红书笔记详情及评论

    Args:
        url: 笔记链接 (https://www.xiaohongshu.com/explore/{note_id})
    """
    ctrl = _get_ctrl()
    return await ctrl.get_note(url)


@mcp.tool()
async def xhs_publish(title: str, content: str, images: list[str]) -> str:
    """发布小红书图文笔记（需登录创作者平台）

    Args:
        title: 笔记标题（不超过20字）
        content: 笔记正文（不超过1000字）
        images: 图片本地路径列表
    """
    ctrl = _get_ctrl()
    return await ctrl.publish_note(title, content, images)


@mcp.tool()
async def xhs_like(url: str) -> str:
    """点赞/取消点赞小红书笔记

    Args:
        url: 笔记链接
    """
    ctrl = _get_ctrl()
    return await ctrl.like_note(url)


@mcp.tool()
async def xhs_comment(url: str, text: str) -> str:
    """评论小红书笔记

    Args:
        url: 笔记链接
        text: 评论内容
    """
    ctrl = _get_ctrl()
    return await ctrl.comment_note(url, text)


@mcp.tool()
async def xhs_user_profile(user_id: str) -> str:
    """获取小红书用户主页信息

    Args:
        user_id: 用户ID
    """
    ctrl = _get_ctrl()
    return await ctrl.user_profile(user_id)


# ── main ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="小红书 MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="传输协议 (默认 stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6789,
        help="SSE 模式端口 (默认 6789)",
    )
    args = parser.parse_args()

    logger.info(f"启动小红书 MCP Server (transport={args.transport})")

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
