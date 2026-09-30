# -*- coding: utf-8 -*-
"""命令行入口：参数解析 + 子命令实现。

四个子命令:
  login [站点...]                打开浏览器手动登录
  sites                          查看已配置站点
  chat <站点|all> [消息]          发送消息 / 交互聊天
  batch <站点|all> <TXT>          从文件（或 stdin）批量发送

输出契约见 console.py：回复正文走 stdout，其余走 stderr。
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import __version__, config
from .browser import ask, open_pages, resolve_url
from .console import (
    EXIT_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    debug,
    die,
    exit_if_failed,
    log,
    out,
    set_level,
    setup_streams,
    warn,
)

SITES: dict = {}
PROMPT = "\n你> "


# ---------------- 输入读取 ----------------


def read_prompt_file(path_arg: str) -> list[str]:
    """读取提示词：`-` 表示从管道读；每行一条，# 开头为注释。"""
    if path_arg == "-":
        content = sys.stdin.read()
        source = "<stdin>"
    else:
        f = Path(path_arg)
        if not f.is_file():
            die(f"文件不存在: {path_arg}", EXIT_ERROR)
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = f.read_text(encoding="gbk", errors="replace")
        source = str(f)
    prompts = [ln.strip() for ln in content.splitlines()]
    prompts = [p for p in prompts if p and not p.startswith("#")]
    if not prompts:
        die(f"{source} 里没有可用的提示词（空行和 # 开头的行会被跳过）", EXIT_ERROR)
    debug(f"从 {source} 读到 {len(prompts)} 条提示词")
    return prompts


def read_stdin_message() -> str:
    msg = sys.stdin.read().strip()
    if not msg:
        die("标准输入是空的（用 `-` 表示从管道读提示词）", EXIT_ERROR)
    return msg


def prompt_input(text: str = PROMPT) -> str:
    """交互模式输入。装了 prompt_toolkit 就有上下箭头历史，没装自动降级。"""
    session = getattr(prompt_input, "_session", None)
    if session is None:
        session = False
        if sys.stdin.isatty():
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.history import FileHistory

                session = PromptSession(history=FileHistory(str(config.history_file())))
            except Exception:  # 未安装或不支持的控制台
                session = False
        prompt_input._session = session  # type: ignore[attr-defined]
    if session:
        return session.prompt(text).strip()
    return input(text).strip()


# ---------------- 子命令 ----------------


def cmd_login(args) -> int:
    keys = args.sites or list(SITES)
    unknown = [k for k in keys if k not in SITES]
    if unknown:
        die(f"未知站点: {', '.join(unknown)}，可用: {config.known_sites()}", EXIT_USAGE)
    with sync_playwright() as pw:
        ctx, _ = open_pages(pw, keys, SITES)
        for k in keys:
            log(f"已打开 {SITES[k]['name']}: {resolve_url(SITES[k])}")
        try:
            input("\n登录完成后按回车关闭浏览器...")
        except (KeyboardInterrupt, EOFError):
            pass
        ctx.close()
    log("登录状态已保存到 browser_profile/，以后无需重复登录。")
    return EXIT_OK


def cmd_sites(args) -> int:
    log(f"配置文件: {config.sites_file()}")
    for k, v in SITES.items():
        out(f"{k:<10} {v['name']:<10} {v['url']}")
    return EXIT_OK


def dump_json(results: list, out_file: str | None) -> None:
    """结果以 JSON 输出到 stdout（--out 时同时写文件）。"""
    text = json.dumps(results, ensure_ascii=False, indent=2)
    out(text)
    if out_file:
        Path(out_file).write_text(text, encoding="utf-8")
        log(f"已写入 {out_file}")


def ask_one(
    site_key: str, message: str, page, json_mode=False, out_file: str | None = None
) -> dict:
    """问一个站点。回复正文写到 stdout；站点名/耗时等装饰信息写到 stderr。"""
    site = SITES[site_key]
    log(f"\n[{site['name']}] 发送中...")
    t0 = time.time()
    reply, err = None, None
    try:
        reply = ask(site_key, message, page, SITES)
    except Exception as e:
        err = str(e)
        warn(f"[{site['name']}] 出错: {err}")
    secs = round(time.time() - t0, 1)

    result = {
        "site": site_key,
        "name": site["name"],
        "message": message,
        "reply": reply,
        "seconds": secs,
        "error": err,
    }

    if not json_mode:
        log(f"[{site['name']}] 回复（耗时 {secs:.0f} 秒）:")
        out(reply if reply else "(未捕获到回复)")  # ← stdout，唯一的内容输出
        if out_file:
            with open(out_file, "a", encoding="utf-8") as f:
                f.write(f"===== {site['name']} =====\n{reply or '(未捕获到回复)'}\n\n")
    return result


def dry_run_report(keys: list[str], prompts: list[str], title: str = "提示词") -> None:
    """--dry-run：把"会做什么"打印到 stdout，不启动浏览器。"""
    out(f"[--dry-run] 未启动浏览器。将使用 {len(keys)} 个站点、{len(prompts)} 条{title}:")
    out("")
    for k in keys:
        s = SITES[k]
        out(
            f"[{s['name']}] {k} → {s['url']}"
            f"（channel={s.get('channel', 'msedge')}, send_method={s.get('send_method', 'enter')}）"
        )
    out("")
    for i, p in enumerate(prompts, 1):
        out(f"{i:>3}. {p}")


def cmd_chat(args) -> int:
    keys = config.resolve_site_arg(args.site, SITES)

    if args.message == "-":
        args.message = read_stdin_message()

    if not args.message:
        if args.dry_run:
            die("--dry-run 需要给出要发送的消息", EXIT_USAGE)
        return interactive(keys, args)

    if args.dry_run:
        dry_run_report(keys, [args.message], title="消息")
        return EXIT_OK

    results = []
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys, SITES)
        try:
            for i, k in enumerate(keys):
                if i and args.delay:
                    log(f"（--delay {args.delay}s 后继续）")
                    time.sleep(args.delay)
                results.append(ask_one(k, args.message, pages[k], args.json, args.out))
        finally:
            ctx.close()

    if args.json:
        dump_json(results, args.out)
    exit_if_failed(results)
    return EXIT_OK


def interactive(keys: list[str], args) -> int:
    """交互聊天模式：反复读一行问一句，q 退出。"""
    log("交互聊天模式（输入 q 退出，Ctrl+C 中断）")
    results = []
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys, SITES)
        try:
            while True:
                try:
                    msg = prompt_input()
                except (KeyboardInterrupt, EOFError):
                    break
                if msg.lower() in ("q", "quit", "exit"):
                    break
                if not msg:
                    continue
                for i, k in enumerate(keys):
                    if i and args.delay:
                        time.sleep(args.delay)
                    results.append(ask_one(k, msg, pages[k], args.json, args.out))
        finally:
            ctx.close()
    if results and args.json:
        dump_json(results, args.out)
    if results:
        exit_if_failed(results)
    return EXIT_OK


def cmd_batch(args) -> int:
    keys = config.resolve_site_arg(args.site, SITES)
    prompts = read_prompt_file(args.file)

    if args.dry_run:
        dry_run_report(keys, prompts)
        return EXIT_OK

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = config.output_dir() / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"共 {len(prompts)} 条提示词，结果将保存到 {out_dir}")

    results = []
    with sync_playwright() as pw:
        ctx, pages = open_pages(pw, keys, SITES)
        try:
            for k in keys:
                site_dir = out_dir / k
                site_dir.mkdir(parents=True, exist_ok=True)
                log(f"\n===== {SITES[k]['name']} =====")
                for i, msg in enumerate(prompts, 1):
                    if i > 1 and args.delay:
                        log(f"（--delay {args.delay}s 后继续）")
                        time.sleep(args.delay)
                    log(f"\n--- 第 {i}/{len(prompts)} 条 ---")
                    r = ask_one(k, msg, pages[k], args.json)
                    results.append(r)
                    (site_dir / f"{i:03d}.txt").write_text(
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
        out(blob)
    if args.out:
        Path(args.out).write_text(blob, encoding="utf-8")
        log(f"已写入 {args.out}")
    exit_if_failed(results)
    return EXIT_OK


# ---------------- 参数解析 ----------------


def _add_logging_flags(parser: argparse.ArgumentParser, suppressed: bool) -> None:
    """把 -q/-v 同时挂到主解析器和各子命令上，两种写法都能用：
         ai-chat-cli -q sites        和        ai-chat-cli sites -q
    子命令那一份用 SUPPRESS 作默认值，避免它把主解析器上已解析好的值覆盖掉。
    """
    default = argparse.SUPPRESS if suppressed else False
    parser.add_argument(
        "-q", "--quiet", action="store_true", default=default, help="安静模式：只输出错误信息"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=default, help="详细模式：输出调试信息"
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_logging_flags(common, suppressed=True)

    ap = argparse.ArgumentParser(
        prog="ai-chat-cli",
        description="AI 聊天命令行工具（豆包 / DeepSeek / 通义千问 / 腾讯元宝 / Kimi）",
        epilog=(
            "示例:\n"
            '  ai-chat-cli chat doubao "帮我写一首关于秋天的诗"\n'
            '  ai-chat-cli chat all "解释一下贝叶斯定理"\n'
            "  ai-chat-cli batch all test_prompts.txt              批量提问\n"
            "  ai-chat-cli batch all test_prompts.txt --dry-run     先看看会问什么\n"
            "  cat questions.txt | ai-chat-cli chat doubao -       从管道读提示词\n"
            '  ai-chat-cli chat doubao --json "问题" > r.json      给脚本用\n'
            "\n"
            "回复正文只从 stdout 输出，进度信息走 stderr。\n"
            "退出码: 0=全部成功  1=运行错误  2=用法错误  3=有站点没拿到回复\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-V", "--version", action="version", version=f"ai-chat-cli {__version__}")
    ap.add_argument(
        "--print-completion",
        choices=["bash", "zsh", "tcsh"],
        help="打印 shell 补全脚本后退出（需要 shtab）",
    )
    _add_logging_flags(ap, suppressed=False)
    # 不用 required=True：否则 --version / --print-completion 这类"不需要子命令"
    # 的选项会被 argparse 拦下来。缺子命令的情况在 main() 里手动报用法错误。
    sub = ap.add_subparsers(dest="cmd", required=False)

    p = sub.add_parser("login", help="打开浏览器手动登录", parents=[common])
    p.add_argument("sites", nargs="*", help="站点名，默认全部")
    p.set_defaults(fn=cmd_login)

    p = sub.add_parser("sites", help="查看已配置站点", parents=[common])
    p.set_defaults(fn=cmd_sites)

    p = sub.add_parser("chat", help="发送消息 / 交互聊天", parents=[common])
    p.add_argument("site", help="站点名或 all")
    p.add_argument(
        "message", nargs="?", default=None, help="消息内容；省略则进入交互模式，`-` 表示从管道读"
    )
    p.add_argument("--json", action="store_true", help="以 JSON 输出结果（便于脚本解析）")
    p.add_argument("--out", metavar="FILE", help="同时把结果写入文件")
    p.add_argument("--dry-run", action="store_true", help="只打印将要执行的计划，不启动浏览器")
    p.add_argument(
        "--delay",
        type=float,
        default=0,
        metavar="SEC",
        help="多个站点之间的间隔秒数（默认 0，批量时建议 2~5，降低风控风险）",
    )
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("batch", help="从 TXT 批量发送", parents=[common])
    p.add_argument("site", help="站点名或 all")
    p.add_argument("file", help="提示词文件（每行一条，# 开头为注释；`-` 表示从管道读）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出汇总")
    p.add_argument("--out", metavar="FILE", help="额外把汇总 JSON 写入指定文件")
    p.add_argument("--dry-run", action="store_true", help="只打印将要执行的计划，不启动浏览器")
    p.add_argument(
        "--delay",
        type=float,
        default=0,
        metavar="SEC",
        help="两条提示词之间的间隔秒数（默认 0，建议 2~5，降低风控风险）",
    )
    p.set_defaults(fn=cmd_batch)

    return ap


def print_completion(ap: argparse.ArgumentParser, shell: str) -> int:
    try:
        import shtab
    except ImportError:
        die("生成补全脚本需要 shtab：pip install shtab", EXIT_ERROR)
    out(shtab.complete(ap, shell=shell))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    setup_streams()
    ap = build_parser()
    try:
        args = ap.parse_args(argv)

        set_level(
            0 if getattr(args, "quiet", False) else (2 if getattr(args, "verbose", False) else 1)
        )

        if getattr(args, "print_completion", None):
            return print_completion(ap, args.print_completion)

        if not getattr(args, "cmd", None):
            ap.print_usage(sys.stderr)
            warn("ai-chat-cli: error: 需要指定子命令（login / sites / chat / batch）")
            return EXIT_USAGE

        global SITES
        SITES = config.load_sites()
        config.ensure_assets()

        return args.fn(args) or EXIT_OK
    except KeyboardInterrupt:
        warn("\n已中断（Ctrl+C）")
        return 130
    except SystemExit as e:
        # argparse 的 --help/--version/用法错误，以及 die() 都走这里，统一转成退出码
        code = e.code
        if isinstance(code, int):
            return code
        return EXIT_OK if code is None else EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
