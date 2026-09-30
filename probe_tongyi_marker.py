# -*- coding: utf-8 -*-
"""找通义千问"用户消息节点"的稳定锚点（用于判断消息是否已进入对话）。"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
CFG = json.loads((BASE / "sites.json").read_text(encoding="utf-8"))
site = CFG["tongyi"]
MARK = "ZZMARK98765"

CHAIN = """(mark) => {
  const out = [];
  const walk = (el) => {
    if (!el.children.length && (el.innerText || '').includes(mark)) {
      const chain = [];
      let n = el;
      for (let i = 0; i < 10 && n && n.tagName; i++) {
        let s = n.tagName.toLowerCase();
        const cls = (n.className || '').toString().trim();
        if (cls) s += '.' + cls.split(/\\s+/).slice(0, 4).join('.');
        for (const a of n.attributes) {
          if (a.name.startsWith('data-')) s += `[${a.name}='${a.value}']`;
        }
        chain.push(s);
        n = n.parentElement;
      }
      out.push(chain);
    }
    for (const c of el.children) walk(c);
  };
  walk(document.body);
  return out;
}"""

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        str(BASE / "browser_profile"), headless=False,
        channel="msedge", no_viewport=True)
    page = ctx.new_page()
    page.goto(site["url"], wait_until="domcontentloaded")
    time.sleep(8)

    inp = page.query_selector("div[contenteditable='true']")
    inp.click()
    time.sleep(0.3)
    page.keyboard.type(f"请回答 {MARK}", delay=25)
    time.sleep(0.3)
    page.keyboard.press("Enter")
    time.sleep(6)

    print("=== 用户消息节点的祖先链（从内到外）===", flush=True)
    for i, chain in enumerate(page.evaluate(CHAIN, MARK)):
        print(f"--- 链 {i+1} ---", flush=True)
        for lvl, s in enumerate(chain):
            print(f"  {'  ' * lvl}{s[:180]}", flush=True)

    print("\n=== 候选计数 ===", flush=True)
    for sel in ["[class*='question']", "[class*='user']", "[class*='bubble']",
                "[class*='message']", "[class*='chat-item']", "[data-testid]",
                ".qk-markdown"]:
        n = page.evaluate("s => document.querySelectorAll(s).length", sel)
        print(f"  {sel:<28} {n}", flush=True)

    ctx.close()
