# -*- coding: utf-8 -*-
"""诊断通义千问：输入框识别、发送判定、回复容器识别。"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
CFG = json.loads((BASE / "sites.json").read_text(encoding="utf-8"))
site = CFG["tongyi"]
MARK = "TESTBARK12345"

DUMP_INPUTS = """() => {
  const out = [];
  document.querySelectorAll("[contenteditable='true'], textarea").forEach(e => {
    const r = e.getBoundingClientRect();
    out.push({tag: e.tagName,
              cls: (e.className || '').toString().slice(0, 100),
              ph: e.getAttribute('placeholder'),
              vis: r.width > 0 && r.height > 0,
              text: (e.innerText || e.value || '').slice(0, 50)});
  });
  return out;
}"""

SNAP = """(sels) => {
  const res = {};
  for (const s of sels) {
    const els = [...document.querySelectorAll(s)];
    res[s] = els.map(e => (e.innerText || '').trim().slice(0, 60));
  }
  const inp = document.querySelector("div[contenteditable='true']");
  res['__input_text'] = inp ? (inp.innerText || '') : null;
  const r = inp ? inp.getBoundingClientRect() : null;
  res['__input_box'] = r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null;
  res['__body_has_mark'] = document.body.innerText.includes('TESTBARK12345');
  return res;
}"""

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    page = ctx.new_page()
    page.goto(site["url"], wait_until="domcontentloaded")
    time.sleep(8)
    print("标题:", page.title(), "| URL:", page.url, flush=True)
    print("输入框候选:", json.dumps(page.evaluate(DUMP_INPUTS), ensure_ascii=False, indent=1), flush=True)

    sels = site["reply_selectors"]
    before = page.evaluate(SNAP, sels)
    print("发送前:", json.dumps(before, ensure_ascii=False)[:800], flush=True)

    inp = page.query_selector("div[contenteditable='true']")
    print("找到输入框:", bool(inp), flush=True)
    if inp:
        inp.click()
        time.sleep(0.4)
        page.keyboard.type(f"请原样回复：{MARK}", delay=25)
        time.sleep(0.4)
        print("输入后 input_text:", repr(page.evaluate(SNAP, sels)["__input_text"])[:200], flush=True)
        page.keyboard.press("Enter")
        print("已按 Enter", flush=True)

        for i in range(1, 31):
            time.sleep(2)
            s = page.evaluate(SNAP, sels)
            print(f"[{i*2}s] input={repr(s['__input_text'])[:60]} "
                  f"mark_in_body={s['__body_has_mark']} "
                  f"qk-markdown={len(s.get('.qk-markdown', []))} "
                  f"last={s.get('.qk-markdown', [''])[-1][:50] if s.get('.qk-markdown') else ''!r}",
                  flush=True)
            if s["__body_has_mark"] and s.get(".qk-markdown") and MARK in str(s[".qk-markdown"]):
                print(">>> 回复已出现", flush=True)
                break

    page.screenshot(path=str(BASE / "test_report" / "diag_tongyi_flow.png"), full_page=False)
    print("截图: test_report/diag_tongyi_flow.png", flush=True)
    ctx.close()
