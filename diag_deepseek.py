# -*- coding: utf-8 -*-
"""诊断：发送后输入框与页面消息的变化时序"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
MSG = "只回复两个字：收到"

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    page = ctx.new_page()
    page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded")
    time.sleep(10)
    inp = page.query_selector("textarea[placeholder*='发送消息']")
    inp.click()
    time.sleep(0.3)
    page.keyboard.type(MSG, delay=30)
    time.sleep(0.5)
    t0 = time.time()
    page.keyboard.press("Enter")
    for i in range(30):
        time.sleep(0.5)
        try:
            val = inp.input_value()
        except Exception as e:
            val = f"<句柄失效 {type(e).__name__}>"
        body = page.evaluate("() => document.body.innerText") or ""
        n_msg = page.evaluate("() => document.querySelectorAll('.ds-message').length")
        n_user = page.evaluate("() => document.querySelectorAll('.ds-message .ds-collapsible-text').length")
        print(f"{time.time()-t0:5.1f}s  输入框值={val!r:30.30}  消息数={n_msg} 用户消息数={n_user} 正文含消息={MSG in body}")
    ctx.close()
