# -*- coding: utf-8 -*-
"""Playwright 页面操作层。

这一层只关心"怎么把一句话发出去、怎么把回复收回来"，不碰命令行参数。
所有站点差异都来自 sites.json，所以网页改版时改配置即可，不用动这里的代码。
"""

from __future__ import annotations

import os
import time

from . import config
from .console import debug, log, warn

# 出现这些字样时视为站点触发了人机验证，需要人工处理
VERIFY_HINTS = (
    "人机验证",
    "安全验证",
    "请选择所有符合",
    "拖动到下方",
    "完成验证",
    "拖动滑块",
    "请完成验证",
)


# ---------------- 启动 ----------------


def resolve_url(site: dict) -> str:
    """把站点 URL 解析成可直接 goto 的地址。

    支持 "file:./xxx.html" 这种相对写法（用于本地 mock 页面），
    这样项目换目录、换电脑、装到 site-packages 都不用改配置。
    """
    url = site["url"]
    if url.startswith("file:") and not url.startswith("file:///"):
        rel = url[5:].lstrip("/\\")
        return (config.data_dir() / rel).resolve().as_uri()
    return url


def launch(pw, channel: str | None = None, headless: bool | None = None):
    """启动可见的持久化浏览器（登录状态保存在 browser_profile/）。

    跨平台兜底：默认用系统 Edge（channel=msedge）；本机没有 Edge 时
    （macOS / Linux 常见）自动退回 Playwright 自带的 Chromium，
    用户不必再手动改 sites.json。
    """
    profile_dir = config.profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)
    headless = config.headless_default() if headless is None else headless
    channel = channel or os.environ.get("AI_CHAT_CLI_CHANNEL") or "msedge"

    attempts: list[str | None] = [channel]
    if channel == "msedge":
        attempts.append(None)  # None = 用 Playwright 自带 chromium

    last_error: Exception | None = None
    for idx, ch in enumerate(attempts):
        kwargs: dict = {"headless": headless}
        if not headless:
            kwargs["no_viewport"] = True  # 跟随窗口大小
        if ch:
            kwargs["channel"] = ch
        try:
            ctx = pw.chromium.launch_persistent_context(str(profile_dir), **kwargs)
            debug(f"浏览器已启动（channel={ch or 'bundled-chromium'}, headless={headless}）")
            return ctx
        except Exception as e:
            last_error = e
            if idx + 1 < len(attempts):
                warn(f"用 {ch} 启动失败，改用 Playwright 自带 Chromium 重试…")
                debug(str(e))

    warn(f"无法启动浏览器（已尝试: {', '.join(str(c) for c in attempts)}）: {last_error}")
    warn("  本机没装 Edge 时（macOS / Linux 常见）：")
    warn("    1) playwright install chromium")
    warn("    2) 也可以设环境变量 AI_CHAT_CLI_CHANNEL=chromium")
    raise SystemExit(1)


# ---------------- 页面元素 ----------------


def find_input(page, selectors):
    """按顺序试选择器，返回第一个可见的元素。"""
    for sel in selectors:
        try:
            for el in page.query_selector_all(sel):
                if el.is_visible():
                    return el
        except Exception:
            pass
    return None


def wait_for_input(page, site: dict, timeout: float = 150):
    """等待输入框出现；首次未登录时用户可在可见窗口里登录，登录后自动继续。"""
    deadline = time.time() + timeout
    start = time.time()
    hinted = False
    while time.time() < deadline:
        el = find_input(page, site["input_selectors"])
        if el:
            return el
        # 页面加载通常几秒，超过 8 秒还找不到才提示，避免正常加载时吓人
        if not hinted and time.time() - start > 8:
            log(
                f"  [提示] 页面仍无输入框，可能需要在浏览器窗口中登录/处理验证，"
                f"最多等待 {timeout:.0f} 秒..."
            )
            hinted = True
        time.sleep(1)
    raise TimeoutError(f"等待输入框超时: {site['name']}")


def has_verification(page) -> bool:
    try:
        txt = page.evaluate("() => document.body.innerText") or ""
    except Exception:
        return False
    return any(h in txt for h in VERIFY_HINTS)


def wait_for_human_verify(page, timeout: float = 300) -> bool:
    """检测到验证时暂停，等用户在可见窗口里手动完成。"""
    log("  [!] 检测到人机验证，请在浏览器窗口中手动完成（程序会自动等待）...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        if not has_verification(page):
            log("  [!] 验证已完成，继续发送。")
            return True
    warn("  [!] 等待验证超时，跳过。")
    return False


def clear_input(page) -> None:
    page.keyboard.press("Control+A")
    time.sleep(0.1)
    page.keyboard.press("Delete")
    time.sleep(0.2)


def input_text_of(el, site: dict | None = None) -> str:
    """取输入框当前文本：textarea 用 value，contenteditable 用 inner_text。

    有些站点（如通义千问）把"向千问提问"这类假 placeholder 直接写进 DOM，
    发送后会重置成这句话。若直接当作"还在输入框里"就会误判消息没发出去，
    所以这里按站点配置把假 placeholder 和不可见字符剔除。
    """
    try:
        tag = el.evaluate("e => e.tagName")
    except Exception:
        return ""
    try:
        if tag in ("TEXTAREA", "INPUT"):
            txt = el.input_value() or ""
        else:
            txt = el.inner_text() or ""
    except Exception:
        return ""
    for ph in (site or {}).get("placeholder_texts", []):
        txt = txt.replace(ph, "")
    txt = txt.replace("\ufeff", "").replace("\u200b", "")
    return txt.strip()


def count_markers(page, selectors) -> int:
    """统计对话消息节点数量。

    用于判断新消息是否已进入对话 —— 有些站点（如 DeepSeek）发送后不清空输入框，
    只能靠"消息节点数 +1"来确认。
    """
    if not selectors:
        return 0
    try:
        return page.evaluate(
            "sels => { for (const s of sels) { const n = document.querySelectorAll(s).length;"
            " if (n) return n; } return 0; }",
            selectors,
        )
    except Exception:
        return 0


def wait_sent(page, inp, site: dict, baseline_count: int, timeout: float = 15) -> bool:
    """判断消息是否已发出：输入框清空 或 对话消息数增加。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not input_text_of(inp, site):
            return True
        if count_markers(page, site.get("sent_marker_selectors", [])) > baseline_count:
            return True
        time.sleep(0.5)
    return False


def send_once(page, site: dict, message: str, input_timeout: float = 150) -> bool:
    """发送一次（不做重发判断）。返回是否确认为已发出。

    重发逻辑放在 ask() 里：只有"没拿到回复"才重发，
    避免因发送判据误判而把同一条消息发两遍。
    """
    inp = wait_for_input(page, site, timeout=input_timeout)
    baseline = count_markers(page, site.get("sent_marker_selectors", []))
    inp.click()
    time.sleep(0.3)
    if input_text_of(inp, site):  # 只在真有残留内容时才清空
        clear_input(page)
    page.keyboard.type(message, delay=20)
    time.sleep(0.3)

    if site.get("send_method", "enter") == "button":
        # 编辑器类页面（如豆包）优先点发送按钮，Enter 可能只是换行
        clicked = False
        for sel in site.get("send_button_selectors", []):
            btn = find_input(page, [sel])
            if btn:
                btn.click()
                clicked = True
                break
        if not clicked:
            page.keyboard.press("Enter")
    else:
        page.keyboard.press("Enter")
    time.sleep(1.5)

    if has_verification(page):
        wait_for_human_verify(page)

    if wait_sent(page, inp, site, baseline):
        return True

    # 兜底：点击发送按钮再确认一次
    for sel in site.get("send_button_selectors", []):
        btn = find_input(page, [sel])
        if btn:
            btn.click()
            time.sleep(2)
            break
    return wait_sent(page, inp, site, baseline, timeout=8)


def get_last_reply(page, selectors) -> str | None:
    """用 evaluate 批量取文本，避免元素句柄因页面重渲染失效。"""
    for sel in selectors:
        try:
            texts = page.eval_on_selector_all(
                sel, "els => els.map(e => (e.innerText || '').trim())"
            )
        except Exception:
            continue
        texts = [t for t in texts if t]
        if texts:
            return texts[-1]
    return None


def wait_reply(page, site: dict, baseline: str, timeout: float | None = None) -> str:
    """轮询最后一条回复，文本连续 stable_seconds 秒不变即认为生成结束。"""
    stable_needed = site.get("stable_seconds", 3)
    timeout = timeout or site.get("reply_timeout", 300)
    last, last_change = "", time.time()
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(0.5)
        t = get_last_reply(page, site["reply_selectors"]) or ""
        if t and t != baseline and t != last:
            last, last_change = t, time.time()
        elif t and t == last and (time.time() - last_change) >= stable_needed:
            return last
    return last


def ask(site_key: str, message: str, page, sites: dict) -> str | None:
    """向指定站点的标签页发一条消息并返回回复（页面由 open_pages 打开并复用）。

    重发策略：先发一次、等回复；**只有确实没拿到回复才重发**（最多 2 次）。
    这样即使"消息是否发出"的判断出错，也不会把同一条消息重复发两遍。
    """
    site = sites[site_key]
    reply_timeout = site.get("reply_timeout", 300)
    baseline = get_last_reply(page, site["reply_selectors"]) or ""

    for attempt in (1, 2):
        try:
            if not send_once(page, site, message, input_timeout=150 if attempt == 1 else 30):
                log("  [提示] 未能确认消息已发出，继续等待回复…")
        except Exception as e:
            warn(f"  [警告] 发送动作异常（第 {attempt} 次）: {e}")
        wait = min(reply_timeout, 120) if attempt == 1 else reply_timeout
        reply = wait_reply(page, site, baseline, timeout=wait)
        if reply:
            return reply
        if attempt == 1:
            log("  [重试] 未收到回复，重新发送一次…")
    return None


def open_pages(pw, keys: list[str], sites: dict):
    """打开一个浏览器，为每个站点开一个标签页（共用 profile，避免互相占用）。"""
    ctx = launch(pw, sites[keys[0]].get("channel", "msedge"))
    pages = {}
    for k in keys:
        page = ctx.new_page()
        page.goto(resolve_url(sites[k]), wait_until="domcontentloaded")
        pages[k] = page
    return ctx, pages
