# -*- coding: utf-8 -*-
"""
AI 聊天命令行工具
通过 Playwright 驱动本机 Edge（可见窗口），向豆包 / DeepSeek 等网页 AI 发消息并取回回复。

用法:
  python main.py login [站点...]        打开浏览器手动登录（登录状态会记住）
  python main.py sites                  查看已配置的站点
  python main.py chat <站点|all> [消息]  发送消息（不带消息则进入交互聊天）
  python main.py batch <站点|all> <文件> 从 TXT 批量发送，回复存到 output/

输出约定（方便写脚本）:
  回复正文 → stdout        可以直接重定向：ai.bat chat doubao "问题" > out.txt
  进度/站点名/耗时 → stderr 不会混进重定向的内容里
  --json  → stdout 输出 JSON 数组（含 site/message/reply/seconds）
  --out F → 同时写入文件
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
PROFILE_DIR = BASE / "browser_profile"
OUTPUT_DIR = BASE / "output"
SITES_FILE = BASE / "sites.json"

# Windows 控制台输出统一为 UTF-8，避免 GBK 报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(msg=""):
    """进度/装饰信息一律走 stderr，保证 stdout 只有回复正文（方便重定向做脚本）"""
    print(msg, file=sys.stderr, flush=True)


def load_sites():
    return json.loads(SITES_FILE.read_text(encoding="utf-8"))


def launch(pw, channel="msedge"):
    """启动可见的持久化浏览器（登录状态保存在 browser_profile/）"""
    PROFILE_DIR.mkdir(exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,          # 有界面，方便登录
        channel=channel,         # 用本机 Edge
        no_viewport=True,        # 跟随窗口大小
    )


# ---------------- 页面操作 ----------------

def find_input(page, selectors):
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                if el.is_visible():
                    return el
        except Exception:
            pass
    return None


def wait_for_input(page, site, timeout=150):
    """等待输入框出现；首次未登录时用户可在可见窗口里登录，登录后自动继续"""
    deadline = time.time() + timeout
    start = time.time()
    hinted = False
    while time.time() < deadline:
        el = find_input(page, site["input_selectors"])
        if el:
            return el
        # 页面加载通常几秒，超过 8 秒还找不到才提示，避免正常加载时吓人
        if not hinted and time.time() - start > 8:
            log(f"  [提示] 页面仍无输入框，可能需要在浏览器窗口中登录/处理验证，"
                f"最多等待 {timeout} 秒...")
            hinted = True
        time.sleep(1)
    raise TimeoutError(f"等待输入框超时: {site['name']}")


# 出现这些字样时视为站点触发了人机验证，需要人工处理
VERIFY_HINTS = ("人机验证", "安全验证", "请选择所有符合", "拖动到下方", "完成验证", "拖动滑块", "请完成验证")


def has_verification(page):
    try:
        txt = page.evaluate("() => document.body.innerText") or ""
    except Exception:
        return False
    return any(h in txt for h in VERIFY_HINTS)


def wait_for_human_verify(page, timeout=300):
    """检测到验证时暂停，等用户在可见窗口里手动完成"""
    log("  [!] 检测到人机验证，请在浏览器窗口中手动完成（程序会自动等待）...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        if not has_verification(page):
            log("  [!] 验证已完成，继续发送。")
            return True
    log("  [!] 等待验证超时，跳过。")
    return False


def clear_input(page):
    page.keyboard.press("Control+A")
    time.sleep(0.1)
    page.keyboard.press("Delete")
    time.sleep(0.2)


def input_text_of(el, site=None):
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


def count_markers(page, selectors):
    """统计对话消息节点数量，用于判断新消息是否已进入对话（部分站点发送后不清空输入框）"""
    if not selectors:
        return 0
    try:
        return page.evaluate(
            "sels => { for (const s of sels) { const n = document.querySelectorAll(s).length; if (n) return n; } return 0; }",
            selectors)
    except Exception:
        return 0


def wait_sent(page, inp, site, baseline_count, timeout=15):
    """判断消息是否已发出：输入框清空 或 对话消息数增加"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not input_text_of(inp, site):
            return True
        if count_markers(page, site.get("sent_marker_selectors", [])) > baseline_count:
            return True
        time.sleep(0.5)
    return False


def send_once(page, site, message, input_timeout=150):
    """发送一次（不做重发判断）。返回是否确认为已发出。

    重发逻辑放在 ask() 里：只有"没拿到回复"才重发，
    避免因发送判据误判而把同一条消息发两遍。
    """
    inp = wait_for_input(page, site, timeout=input_timeout)
    baseline = count_markers(page, site.get("sent_marker_selectors", []))
    inp.click()
    time.sleep(0.3)
    if input_text_of(inp, site):          # 只在真有残留内容时才清空
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
    if wait_sent(page, inp, site, baseline, timeout=8):
        return True
    return False


def get_last_reply(page, selectors):
    """用 evaluate 批量取文本，避免元素句柄因页面重渲染失效"""
    for sel in selectors:
        try:
            texts = page.eval_on_selector_all(
                sel, "els => els.map(e => (e.innerText || '').trim())")
        except Exception:
            continue
        texts = [t for t in texts if t]
        if texts:
            return texts[-1]
    return None


def wait_reply(page, site, baseline, timeout=None):
    """轮询最后一条回复，文本连续 stable_seconds 秒不变即认为生成结束"""
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


def ask(pw, site_key, message, page):
    """向指定站点的标签页发一条消息并返回回复（页面由 open_pages 打开并复用）。

    重发策略：先发一次、等回复；**只有确实没拿到回复才重发**（最多 2 次）。
    这样即使"消息是否发出"的判断出错，也不会把同一条消息重复发两遍。
    """
    site = SITES[site_key]
    reply_timeout = site.get("reply_timeout", 300)
    baseline = get_last_reply(page, site["reply_selectors"]) or ""

    for attempt in (1, 2):
        try:
            if not send_once(page, site, message, input_timeout=150 if attempt == 1 else 30):
                log("  [提示] 未能确认消息已发出，继续等待回复…")
        except Exception as e:
            log(f"  [警告] 发送动作异常（第 {attempt} 次）: {e}")
        wait = min(reply_timeout, 120) if attempt == 1 else reply_timeout
        reply = wait_reply(page, site, baseline, timeout=wait)
        if reply:
            return reply
        if attempt == 1:
            log("  [重试] 未收到回复，重新发送一次…")
    return None


def resolve_url(site):
    """把站点 URL 解析成可直接 goto 的地址。

    支持 "file:./xxx.html" 这种相对写法（用于本地 mock 页面），
    这样项目换目录、换电脑都不用改配置。
    """
    url = site["url"]
    if url.startswith("file:") and not url.startswith("file:///"):
        rel = url[5:].lstrip("/\\")
        return (BASE / rel).as_uri()
    return url


def open_pages(pw, keys):
    """打开一个浏览器，为每个站点开一个标签页（共用 profile，避免互相占用）"""
    ctx = launch(pw, SITES[keys[0]].get("channel", "msedge"))
    pages = {}
    for k in keys:
        page = ctx.new_page()
        page.goto(resolve_url(SITES[k]), wait_until="domcontentloaded")
        pages[k] = page
    return ctx, pages


# ---------------- 命令 ----------------

def cmd_login(args):
    keys = args.sites or list(SITES)
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys)
        for k in keys:
            print(f"已打开 {SITES[k]['name']}: {resolve_url(SITES[k])}")
        try:
            input("\n登录完成后按回车关闭浏览器...")
        except (KeyboardInterrupt, EOFError):
            pass
        ctx.close()
    print("登录状态已保存到 browser_profile/，以后无需重复登录。")


def cmd_sites(args):
    for k, v in SITES.items():
        print(f"{k:<10} {v['name']:<10} {v['url']}")


def dump_json(results, out=None):
    """结果以 JSON 输出到 stdout（--out 时同时写文件）"""
    text = json.dumps(results, ensure_ascii=False, indent=2)
    print(text, flush=True)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        log(f"已写入 {out}")


def _ask_one(pw, key, message, page, json_mode=False, out=None):
    """问一个站点。回复正文写到 stdout；站点名/耗时等装饰信息写到 stderr。"""
    site = SITES[key]
    log(f"\n[{site['name']}] 发送中...")
    t0 = time.time()
    reply, err = None, None
    try:
        reply = ask(pw, key, message, page)
    except Exception as e:
        err = str(e)
        log(f"[{site['name']}] 出错: {err}")
    secs = round(time.time() - t0, 1)

    result = {"site": key, "name": site["name"], "message": message,
              "reply": reply, "seconds": secs, "error": err}

    if not json_mode:
        log(f"[{site['name']}] 回复（耗时 {secs:.0f} 秒）:")
        print(reply if reply else "(未捕获到回复)", flush=True)   # ← stdout，唯一的内容输出
    if out and not json_mode:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"===== {site['name']} =====\n{reply or '(未捕获到回复)'}\n\n")
    return result


def cmd_chat(args):
    keys = list(SITES) if args.site == "all" else [args.site]
    if args.site != "all" and args.site not in SITES:
        print(f"未知站点: {args.site}，可用: {', '.join(SITES)} | all")
        sys.exit(1)

    results = []
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys)
        try:
            if args.message:  # 单次问答
                for k in keys:
                    results.append(_ask_one(pw, k, args.message, pages[k],
                                            args.json, args.out))
            else:             # 交互模式
                log("交互聊天模式（输入 q 退出）")
                while True:
                    try:
                        msg = input("\n你> ").strip()
                    except (KeyboardInterrupt, EOFError):
                        break
                    if msg.lower() in ("q", "quit", "exit"):
                        break
                    if not msg:
                        continue
                    for k in keys:
                        results.append(_ask_one(pw, k, msg, pages[k],
                                                args.json, args.out))
        finally:
            ctx.close()

    if args.json:
        dump_json(results, args.out)


def cmd_batch(args):
    keys = list(SITES) if args.site == "all" else [args.site]
    if args.site != "all" and args.site not in SITES:
        print(f"未知站点: {args.site}，可用: {', '.join(SITES)} | all")
        sys.exit(1)

    prompts = []
    f = Path(args.file)
    if not f.is_file():
        print(f"文件不存在: {args.file}")
        sys.exit(1)
    try:
        content = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = f.read_text(encoding="gbk", errors="replace")
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            prompts.append(line)
    if not prompts:
        print("文件里没有可用的提示词（空行和 # 开头的行会被跳过）")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"共 {len(prompts)} 条提示词，结果将保存到 {out_dir}")

    results = []
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys)
        try:
            for k in keys:
                site = SITES[k]
                site_dir = out_dir / k
                site_dir.mkdir(parents=True, exist_ok=True)
                log(f"\n===== {site['name']} =====")
                for i, msg in enumerate(prompts, 1):
                    log(f"\n--- 第 {i}/{len(prompts)} 条 ---")
                    r = _ask_one(pw, k, msg, pages[k], args.json)
                    results.append(r)
                    out_file = site_dir / f"{i:03d}.txt"
                    out_file.write_text(
                        f"提问：{msg}\n\n回复：\n{r['reply'] or '(未捕获到回复)'}\n",
                        encoding="utf-8",
                    )
        finally:
            ctx.close()

    blob = json.dumps(results, ensure_ascii=False, indent=2)
    (out_dir / "summary.json").write_text(blob, encoding="utf-8")
    log(f"\n批处理完成，结果目录: {out_dir}")
    log(f"结构化汇总: {out_dir / 'summary.json'}")
    if args.json:
        print(blob, flush=True)
    if args.out:
        Path(args.out).write_text(blob, encoding="utf-8")
        log(f"已写入 {args.out}")


def main():
    global SITES
    SITES = load_sites()

    ap = argparse.ArgumentParser(description="AI 聊天命令行工具（豆包/DeepSeek 等）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("login", help="打开浏览器手动登录")
    p.add_argument("sites", nargs="*", help="站点名，默认全部")
    p.set_defaults(fn=cmd_login)

    p = sub.add_parser("sites", help="查看已配置站点")
    p.set_defaults(fn=cmd_sites)

    p = sub.add_parser("chat", help="发送消息 / 交互聊天")
    p.add_argument("site", help="站点名或 all")
    p.add_argument("message", nargs="?", default=None, help="消息内容；省略则进入交互模式")
    p.add_argument("--json", action="store_true", help="以 JSON 输出结果（便于脚本解析）")
    p.add_argument("--out", metavar="FILE", help="同时把结果写入文件")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("batch", help="从 TXT 批量发送")
    p.add_argument("site", help="站点名或 all")
    p.add_argument("file", help="提示词文件（每行一条，# 开头为注释）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出汇总")
    p.add_argument("--out", metavar="FILE", help="额外把汇总 JSON 写入指定文件")
    p.set_defaults(fn=cmd_batch)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
