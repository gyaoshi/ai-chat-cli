# -*- coding: utf-8 -*-
"""豆包专项探测：找发送按钮 + 抓回复容器；遇人机验证会暂停等待人工完成"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
OUT = BASE / "test_report"
OUT.mkdir(exist_ok=True)
MARK = "收到"
MSG = "请回复两个字：收到"

VERIFY_HINTS = ("人机验证", "安全验证", "请选择所有符合", "拖动到下方", "完成验证", "拖动滑块", "请完成验证")

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    page = ctx.new_page()
    page.goto("https://www.doubao.com/chat/", wait_until="domcontentloaded")
    time.sleep(12)

    # 1. 找输入框
    inp = None
    for el in page.query_selector_all("div.tiptap.ProseMirror[contenteditable='true']"):
        if el.is_visible():
            inp = el
            break
    if not inp:
        print("找不到输入框")
        ctx.close()
        raise SystemExit

    # 2. 输入消息
    inp.click()
    time.sleep(0.5)
    page.keyboard.type(MSG, delay=40)
    time.sleep(1.5)
    page.screenshot(path=str(OUT / "doubao_typed.png"))

    # 3. 找发送按钮候选
    btns = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('[data-testid],button,div[role="button"]').forEach(el => {
        const t = (el.getAttribute('data-testid') || '') + '|' + (el.getAttribute('aria-label') || '') + '|' + (el.className && el.className.toString ? el.className.toString() : '');
        if (/send|发送|submit/i.test(t)) {
          out.push({testid: el.getAttribute('data-testid'), aria: el.getAttribute('aria-label'), tag: el.tagName,
                    cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0,80),
                    visible: el.offsetParent !== null});
        }
      });
      return out;
    }""")
    print("发送按钮候选:", json.dumps(btns, ensure_ascii=False))
    (OUT / "doubao_send_buttons.json").write_text(json.dumps(btns, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. 发送（优先点发送按钮，找不到才按 Enter）
    clicked = False
    for sel in ["[data-testid='chat_input_send_button']", "#flow-end-msg-send",
                "button[aria-label*='发送']", "div[data-testid='send-button']"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                clicked = True
                print("已点发送按钮:", sel)
                break
        except Exception:
            pass
    if not clicked:
        page.keyboard.press("Enter")
        print("已按 Enter 发送")

    # 5. 等待回复 / 处理验证
    ok = False
    for i in range(40):
        time.sleep(3)
        txt = page.evaluate("() => document.body.innerText") or ""
        if any(h in txt for h in VERIFY_HINTS):
            print("[!] 检测到人机验证，请在浏览器窗口中手动完成（等待最多 300 秒）...", flush=True)
            for _ in range(100):
                time.sleep(3)
                t2 = page.evaluate("() => document.body.innerText") or ""
                if not any(h in t2 for h in VERIFY_HINTS):
                    print("[!] 验证完成", flush=True)
                    break
            continue
        if txt.count(MARK) >= 2:
            ok = True
            break
    print("回复状态:", "已出现" if ok else "未检测到")

    time.sleep(4)
    html = page.evaluate("() => document.body.innerHTML")
    (OUT / "doubao_reply.html").write_text(html, encoding="utf-8")
    page.screenshot(path=str(OUT / "doubao_reply.png"))
    ctx.close()
print("done")
