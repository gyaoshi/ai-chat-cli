# -*- coding: utf-8 -*-
"""真实发送探测：向站点发一条消息，抓取回复 DOM 结构"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
CFG = json.loads((BASE / "sites.json").read_text(encoding="utf-8"))
OUT = BASE / "test_report"
OUT.mkdir(exist_ok=True)

MARK = "TESTBARK12345"

INPUTS = {
    "doubao": ["div.tiptap.ProseMirror[contenteditable='true']", "div[contenteditable='true']"],
    "deepseek": ["textarea[placeholder*='发送消息']", "textarea[placeholder*='DeepSeek']", "textarea"],
    "tongyi": ["div[contenteditable='true']"],
    "yuanbao": ["div.ql-editor[contenteditable='true']", "div[contenteditable='true']"],
    "kimi": ["div.chat-input-editor[contenteditable='true']", "div[contenteditable='true']"],
}

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    for k in sys.argv[1:]:
        site = CFG[k]
        page = ctx.new_page()
        try:
            page.goto(site["url"], wait_until="domcontentloaded")
            time.sleep(site.get("load_wait", 6) + 4)
            inp = None
            for sel in INPUTS[k]:
                els = [e for e in page.query_selector_all(sel) if e.is_visible()]
                if els:
                    inp = els[-1]
                    print(f"[{k}] 输入框: {sel}")
                    break
            if not inp:
                print(f"[{k}] 找不到输入框")
                continue
            inp.click()
            time.sleep(0.5)
            page.keyboard.type(f"请原样回复这串字符：{MARK}", delay=30)
            time.sleep(0.3)
            inp.press("Enter")
            print(f"[{k}] 已发送，等待回复...")
            deadline = time.time() + 60
            found = False
            while time.time() < deadline:
                time.sleep(2)
                txt = page.evaluate("() => document.body.innerText")
                inp_txt = inp.inner_text()
                if txt.count(MARK) >= 2 and MARK not in inp_txt:
                    found = True
                    break
            time.sleep(5)  # 等流式结束
            html = page.evaluate("() => document.body.innerHTML")
            (OUT / f"{k}_reply.html").write_text(html, encoding="utf-8")
            page.screenshot(path=str(OUT / f"{k}_reply.png"))
            print(f"[{k}] 回复{'已出现' if found else '未检测到(可能需登录)'}，DOM 已保存")
        except Exception as e:
            print(f"[{k}] 出错: {e}")
        finally:
            page.close()
    ctx.close()
print("done")
