# -*- coding: utf-8 -*-
"""实站 DOM 检查：抓取输入框/回复容器的真实结构，输出 JSON + 截图"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
CFG = json.loads((BASE / "sites.json").read_text(encoding="utf-8"))
OUT = BASE / "test_report"
OUT.mkdir(exist_ok=True)

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

keys = sys.argv[1:] or ["tongyi", "yuanbao", "kimi"]
with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    for k in keys:
        site = CFG[k]
        page = ctx.new_page()
        try:
            page.goto(site["url"], wait_until="domcontentloaded")
            time.sleep(site.get("load_wait", 6) + 6)
            info = page.evaluate(DUMP_JS)
            (OUT / f"{k}.json").write_text(
                json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            page.screenshot(path=str(OUT / f"{k}.png"))
            print(f"[{k}] OK -> {k}.json / {k}.png  标题: {info['title']}")
        except Exception as e:
            print(f"[{k}] 出错: {e}")
        finally:
            page.close()
    ctx.close()
print("done")
