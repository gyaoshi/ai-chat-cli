# -*- coding: utf-8 -*-
"""打开站点等你登录。浏览器窗口会一直保留，你手动关掉窗口后才退出并保存登录态。

用法:
  python login_keep.py [站点...]            默认保留 60 分钟
  python login_keep.py --minutes 180        保留 180 分钟
  python login_keep.py --forever            不限时，直到你关掉窗口

提示: 直接双击 login.bat 运行最方便（窗口在你自己的终端里，不会被别的程序影响）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent
CFG = json.loads((BASE / "sites.json").read_text(encoding="utf-8"))

ap = argparse.ArgumentParser(description="打开站点等你登录，关掉窗口才退出")
ap.add_argument("sites", nargs="*", help="站点名，默认全部")
ap.add_argument("--minutes", type=float, default=60,
                help="最长保留多少分钟（默认 60）")
ap.add_argument("--forever", action="store_true", help="不限时，直到你关闭窗口")
args = ap.parse_args()

keys = [k for k in (args.sites or list(CFG)) if k in CFG]
if not keys:
    print(f"没有可用站点，可选: {', '.join(CFG)}")
    sys.exit(1)

deadline = None if args.forever else time.time() + args.minutes * 60

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)

    for k in keys:
        page = ctx.new_page()
        url = CFG[k]["url"]
        if url.startswith("file:") and not url.startswith("file:///"):
            url = (BASE / url[5:].lstrip("/\\")).as_uri()
        page.goto(url, wait_until="domcontentloaded")
        print(f"已打开 {CFG[k]['name']}: {url}", flush=True)

    if deadline:
        print(f"\n窗口会保留 {args.minutes:.0f} 分钟，不用着急，慢慢登录。", flush=True)
    else:
        print("\n窗口会一直保留，不用着急，慢慢登录。", flush=True)
    print("👉 登录完成后直接关闭浏览器窗口即可（登录状态自动保存）。\n", flush=True)

    last_tick = time.time()
    empty_streak = 0
    try:
        while True:
            time.sleep(2)
            # 判断窗口是否还活着：取不到 ctx.pages 或所有页面都不可用 → 视为已关闭
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
                    print(f"  ...窗口保持中，剩余 {left // 60} 分 {left % 60} 秒"
                          f"（随时可关闭窗口结束）", flush=True)
                else:
                    print("  ...窗口保持中（关闭窗口即可结束）", flush=True)

            if deadline and time.time() > deadline:
                print(f"\n已到 {args.minutes:.0f} 分钟上限，自动关闭。"
                      f"如需更久请用 --minutes 或 --forever。", flush=True)
                break
    except KeyboardInterrupt:
        pass

print("\n浏览器已关闭，登录状态已保存到 browser_profile/", flush=True)
