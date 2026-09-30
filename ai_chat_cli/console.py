# -*- coding: utf-8 -*-
"""终端输出的唯一约定层。

约定（README 里对外承诺过，不要在别处破坏）:
  stdout → 只放"回复正文"（或 --json / --dry-run 的结构化结果）
  stderr → 进度、站点名、耗时、警告、错误

日志级别:
  -q/--quiet   → 0，只显示错误
  默认         → 1，显示进度
  -v/--verbose → 2，追加调试信息
"""

from __future__ import annotations

import sys

# 退出码语义（脚本按这个判断成败）
EXIT_OK = 0  # 全部成功
EXIT_ERROR = 1  # 运行错误：配置缺失、提示词文件不存在等
EXIT_USAGE = 2  # 用法错误（argparse 默认）
EXIT_SITE_FAILED = 3  # 至少一个站点没拿到回复

QUIET, NORMAL, VERBOSE = 0, 1, 2

_level = NORMAL


def setup_streams() -> None:
    """Windows 控制台统一 UTF-8，避免中文/emoji 触发 GBK 编码错误。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # 已被重定向到不支持 reconfigure 的对象
                pass


def set_level(level: int) -> None:
    global _level
    _level = level


def get_level() -> int:
    return _level


def log(msg: str = "", level: int = NORMAL) -> None:
    """进度/装饰信息一律走 stderr，保证 stdout 只有内容。"""
    if _level >= level:
        print(msg, file=sys.stderr, flush=True)


def debug(msg: str) -> None:
    log(f"[debug] {msg}", level=VERBOSE)


def warn(msg: str) -> None:
    """警告：quiet 模式下也会显示（用户需要知道出了问题）。"""
    log(msg, level=QUIET)


def die(msg: str, code: int = EXIT_ERROR):
    """致命错误：信息走 stderr（不污染 stdout），并以指定退出码结束。"""
    warn(msg)
    sys.exit(code)


def out(text: str) -> None:
    """内容输出：唯一允许写 stdout 的入口。"""
    print(text, flush=True)


def exit_if_failed(results: list) -> None:
    """有任何站点没拿到回复就以 EXIT_SITE_FAILED 结束，方便脚本一次性判断成败。"""
    bad = [r for r in results if r.get("error") or not r.get("reply")]
    if bad:
        names = "、".join(r.get("name") or r.get("site", "?") for r in bad)
        warn(f"\n{len(bad)}/{len(results)} 个站点未成功: {names}（退出码 {EXIT_SITE_FAILED}）")
        sys.exit(EXIT_SITE_FAILED)
