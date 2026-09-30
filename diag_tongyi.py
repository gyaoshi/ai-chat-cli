# -*- coding: utf-8 -*-
"""诊断通义：打开页面后逐秒观察输入框可见性 + 截图"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
OUT = BASE / "test_report"

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    page = ctx.new_page()
    page.goto("https://www.qianwen.com/", wait_until="domcontentloaded")
    for i in range(20):
        time.sleep(1)
        info = page.evaluate("""() => {
          const es = [...document.querySelectorAll("div[contenteditable='true']")];
          const vis = es.filter(e => e.offsetParent !== null);
          const body = document.body.innerText || '';
          return {total: es.length, visible: vis.length,
                  login_word: /登录|扫码|立即体验/.test(body.slice(0, 600)),
                  head: body.replace(/\\s+/g,' ').slice(0, 120)};
        }""")
        print(f"{i+1:2}s 可编辑={info['total']} 可见={info['visible']} 头部文案: {info['head']}")
        if i == 14:
            page.screenshot(path=str(OUT / "tongyi_diag.png"))
    page.screenshot(path=str(OUT / "tongyi_diag2.png"))
    ctx.close()
