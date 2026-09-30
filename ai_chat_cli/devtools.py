# -*- coding: utf-8 -*-
"""维护类小工具（仓库用户才会用到，不随 pip 包安装）。

  kill_stale     结束占用 browser_profile 的残留 Edge 进程
  clean_cache    只删浏览器缓存，保留登录状态
  login_window   登录专用窗口（保留 N 分钟，关窗即保存）
  inspect_site   抓站点真实 DOM + 截图（网页改版时排查用）
  probe_send     真发一条消息验证选择器，并 dump 回复 DOM

仓库根目录下的同名脚本只是这里的薄壳，方便 `python kill_stale.py` 直接跑。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import config
from .browser import launch, resolve_url
from .console import EXIT_ERROR, EXIT_OK, log, setup_streams

# ---------------- 残留进程 ----------------


def kill_stale() -> str | None:
    """结束所有使用本项目 browser_profile 的 Edge 进程，返回结束数量（失败返回 None）。"""
    profile = str(config.profile_dir())
    if os.name != "nt":
        log("kill_stale 只在 Windows 上有效（其他系统的残留进程不会被 profile 独占锁住）")
        return None
    escaped = profile.replace("\\", "\\\\")
    ps = (
        "$procs = Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{escaped}*' }}; "
        "$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "Write-Output $procs.Count"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"PowerShell 报错: {r.stderr}")
    lines = (r.stdout or "").strip().splitlines()
    return lines[-1] if lines else None


def main_kill_stale(argv: list[str] | None = None) -> int:
    setup_streams()
    log(f"已结束占用 browser_profile 的 Edge 进程数: {kill_stale()}")
    return EXIT_OK


# ---------------- 缓存清理 ----------------

# 可安全删除的缓存/遥测目录或文件（相对 browser_profile）
CACHE_TARGETS = [
    "BrowserMetrics",
    "DeferredBrowserMetrics",
    "GrShaderCache",
    "ShaderCache",
    "GraphiteDawnCache",
    "GPUPersistentCache",
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/DawnWebGPUCache",
    "Default/DawnGraphiteCache",
    "Default/Service Worker/CacheStorage",
    "Default/load_statistics.db",
    "Default/settings_diagnostic.log",
    "Default/favorites_diagnostic.log",
]

# 这些是登录凭据，永远不删
KEEP_TARGETS = [
    "Default/Network/Cookies",
    "Default/Local Storage",
    "Default/IndexedDB",
    "Default/Session Storage",
    "Default/Login Data",
    "Default/Preferences",
    "Local State",
]


def dir_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _force_rm(func, path, exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        log(f"    跳过 {path}: {e}")


def main_clean_cache(argv: list[str] | None = None) -> int:
    setup_streams()
    ap = argparse.ArgumentParser(description="清理 browser_profile 缓存（保留登录状态）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不删除")
    args = ap.parse_args(argv)

    profile = config.profile_dir()
    if not profile.exists():
        log(f"{profile} 不存在，无需清理。")
        return EXIT_OK

    total = dir_size(profile)
    log(f"当前 browser_profile 体积: {total / 1024 / 1024:.1f} MB")

    if not args.dry_run:
        log(f"已结束占用 profile 的 Edge 进程数: {kill_stale()}")

    freed = 0
    log("\n缓存项:")
    for rel in CACHE_TARGETS:
        p = profile / rel
        if not p.exists():
            continue
        sz = dir_size(p)
        freed += sz
        tag = "（将删除）" if not args.dry_run else ""
        log(f"  {sz / 1024 / 1024:>8.1f} MB  {rel}{tag}")
        if not args.dry_run:
            if p.is_file():
                p.unlink(missing_ok=True)
            else:
                shutil.rmtree(p, onerror=_force_rm)

    log("\n保留的登录凭据:")
    for k in KEEP_TARGETS:
        if (profile / k).exists():
            log(f"  {k}")

    if args.dry_run:
        log(f"\n[dry-run] 可释放约 {freed / 1024 / 1024:.1f} MB。去掉 --dry-run 即执行删除。")
    else:
        after = dir_size(profile)
        log(
            f"\n清理完成：释放 {freed / 1024 / 1024:.1f} MB，"
            f"现在 {after / 1024 / 1024:.1f} MB。登录状态保持不变。"
        )
    return EXIT_OK


# ---------------- 登录窗口 ----------------


def main_login_window(argv: list[str] | None = None) -> int:
    """打开站点等你登录。窗口保留到你关闭它（或到时间上限）才退出并保存登录态。"""
    setup_streams()
    ap = argparse.ArgumentParser(description="打开站点等你登录，关掉窗口才退出")
    ap.add_argument("sites", nargs="*", help="站点名，默认全部")
    ap.add_argument("--minutes", type=float, default=60, help="最长保留多少分钟（默认 60）")
    ap.add_argument("--forever", action="store_true", help="不限时，直到你关闭窗口")
    args = ap.parse_args(argv)

    sites = config.load_sites()
    keys = [k for k in (args.sites or list(sites)) if k in sites]
    if not keys:
        log(f"没有可用站点，可选: {', '.join(sites)}")
        return EXIT_ERROR

    deadline = None if args.forever else time.time() + args.minutes * 60

    with sync_playwright() as pw:
        ctx = launch(pw, sites[keys[0]].get("channel", "msedge"))
        for k in keys:
            page = ctx.new_page()
            page.goto(resolve_url(sites[k]), wait_until="domcontentloaded")
            log(f"已打开 {sites[k]['name']}: {resolve_url(sites[k])}")

        if deadline:
            log(f"\n窗口会保留 {args.minutes:.0f} 分钟，不用着急，慢慢登录。")
        else:
            log("\n窗口会一直保留，不用着急，慢慢登录。")
        log("👉 登录完成后直接关闭浏览器窗口即可（登录状态自动保存）。\n")

        last_tick = time.time()
        empty_streak = 0
        try:
            while True:
                time.sleep(2)
                # 判断窗口是否还活着：取不到 ctx.pages，或所有页面都不可用 → 视为已关闭
                try:
                    pages = ctx.pages
                except Exception:
                    break
                alive = False
                for p in pages:
                    try:
                        p.title()
                        alive = True
                        break
                    except Exception:
                        continue
                if alive:
                    empty_streak = 0
                else:
                    empty_streak += 1
                    if empty_streak >= 2:
                        break

                if time.time() - last_tick >= 30:
                    last_tick = time.time()
                    if deadline:
                        left = max(0, int(deadline - time.time()))
                        log(
                            f"  ...窗口保持中，剩余 {left // 60} 分 {left % 60} 秒"
                            f"（随时可关闭窗口结束）"
                        )
                    else:
                        log("  ...窗口保持中（关闭窗口即可结束）")

                if deadline and time.time() > deadline:
                    log(
                        f"\n已到 {args.minutes:.0f} 分钟上限，自动关闭。"
                        f"如需更久请用 --minutes 或 --forever。"
                    )
                    break
        except KeyboardInterrupt:
            pass

    log("\n浏览器已关闭，登录状态已保存到 browser_profile/")
    return EXIT_OK


# ---------------- DOM 排查 ----------------

DUMP_JS = """() => {
  const dump = el => ({
    tag: el.tagName,
    id: el.id,
    cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0, 150),
    ph: el.getAttribute('placeholder'),
    testid: el.getAttribute('data-testid'),
    ce: el.getAttribute('contenteditable'),
    visible: el.offsetParent !== null
  });
  return {
    url: location.href,
    title: document.title,
    textareas: [...document.querySelectorAll('textarea')].map(dump),
    editables: [...document.querySelectorAll('[contenteditable="true"]')].map(dump),
    inputs: [...document.querySelectorAll('[data-testid]')].slice(0, 30).map(dump)
  };
}"""


def report_dir() -> Path:
    """排查产物（截图 / DOM dump）放这里，已被 .gitignore 排除。"""
    return config.data_dir() / "test_report"


def main_inspect_site(argv: list[str] | None = None) -> int:
    setup_streams()
    sites = config.load_sites()
    keys = argv or ["tongyi", "yuanbao", "kimi"]
    out = report_dir()
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = launch(pw, sites[keys[0]].get("channel", "msedge"))
        for k in keys:
            site = sites[k]
            page = ctx.new_page()
            try:
                page.goto(resolve_url(site), wait_until="domcontentloaded")
                time.sleep(site.get("load_wait", 6) + 6)
                info = page.evaluate(DUMP_JS)
                (out / f"{k}.json").write_text(
                    json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                page.screenshot(path=str(out / f"{k}.png"))
                log(f"[{k}] OK -> {k}.json / {k}.png  标题: {info['title']}")
            except Exception as e:
                log(f"[{k}] 出错: {e}")
            finally:
                page.close()
        ctx.close()
    log(f"完成，报告在 {out}")
    return EXIT_OK


MARK = "TESTBARK12345"


def main_probe_send(argv: list[str] | None = None) -> int:
    setup_streams()
    keys = list(argv or [])
    if not keys:
        log("用法: probe_send.py <站点...>   （例: python probe_send.py doubao）")
        return EXIT_ERROR

    sites = config.load_sites()
    out = report_dir()
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = launch(pw, sites[keys[0]].get("channel", "msedge"))
        for k in keys:
            site = sites[k]
            page = ctx.new_page()
            try:
                page.goto(resolve_url(site), wait_until="domcontentloaded")
                time.sleep(site.get("load_wait", 6) + 4)
                inp = None
                for sel in site["input_selectors"]:
                    els = [e for e in page.query_selector_all(sel) if e.is_visible()]
                    if els:
                        inp = els[-1]
                        log(f"[{k}] 输入框: {sel}")
                        break
                if not inp:
                    log(f"[{k}] 找不到输入框")
                    continue
                inp.click()
                time.sleep(0.5)
                page.keyboard.type(f"请原样回复这串字符：{MARK}", delay=30)
                time.sleep(0.3)
                inp.press("Enter")
                log(f"[{k}] 已发送，等待回复...")
                deadline = time.time() + 60
                found = False
                while time.time() < deadline:
                    time.sleep(2)
                    txt = page.evaluate("() => document.body.innerText")
                    if txt.count(MARK) >= 2 and MARK not in inp.inner_text():
                        found = True
                        break
                time.sleep(5)  # 等流式结束
                (out / f"{k}_reply.html").write_text(
                    page.evaluate("() => document.body.innerHTML"), encoding="utf-8"
                )
                page.screenshot(path=str(out / f"{k}_reply.png"))
                log(f"[{k}] 回复{'已出现' if found else '未检测到(可能需登录)'}，DOM 已保存")
            except Exception as e:
                log(f"[{k}] 出错: {e}")
            finally:
                page.close()
        ctx.close()
    log(f"完成，报告在 {out}")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main_kill_stale())
