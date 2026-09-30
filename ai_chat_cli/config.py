# -*- coding: utf-8 -*-
"""路径与配置解析 —— 全项目唯一回答"我在哪、配置在哪"的地方。

为什么单独一层:
  以前到处写 `Path(__file__).parent / "sites.json"`。一旦用 pip / pipx 装进
  site-packages，那个位置就不该再被写入（配置会随升级被覆盖），而且也找不到
  用户自己的改动。所以统一按下面的优先级解析，同时兼顾两种用法:

  1) git clone 直接跑   → 用仓库根目录的 sites.json，familiar 的旧行为不变
  2) pipx install 安装   → 用用户目录 %APPDATA%/ai-chat-cli/sites.json，
                          首次运行从包内自带的默认配置复制一份出来

环境变量覆盖（测试和 CI 用得上）:
  AI_CHAT_CLI_HOME    数据目录（browser_profile / output / 默认配置）
  AI_CHAT_CLI_SITES   直接指定 sites.json 的路径
  AI_CHAT_CLI_CHANNEL 浏览器内核，默认 msedge
  AI_CHAT_CLI_HEADLESS=1  无界面运行（CI 用）
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .console import EXIT_USAGE, debug, die

APP_NAME = "ai-chat-cli"
PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_DIR = PACKAGE_DIR / "data"

# 首次运行会自动复制到数据目录的"随包资源"
BUNDLED_ASSETS = ("test_mock.html", "test_prompts.txt")

_sites_cache: dict | None = None


# ---------------- 目录解析 ----------------


def user_config_dir() -> Path:
    """用户级配置目录（跨平台）: Windows 用 %APPDATA%，其他用 XDG。"""
    override = os.environ.get("AI_CHAT_CLI_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / APP_NAME


def repo_root() -> Path | None:
    """如果是 git clone 出来的仓库就返回仓库根目录，否则 None。

    判据：包的上一层同时有 pyproject.toml 和 sites.json。
    wheel 安装到 site-packages 时不满足，自然落到用户目录。
    """
    parent = PACKAGE_DIR.parent
    if (parent / "pyproject.toml").is_file() and (parent / "sites.json").is_file():
        return parent
    return None


def data_dir() -> Path:
    """运行时数据目录（browser_profile / output 放这里）。"""
    env = os.environ.get("AI_CHAT_CLI_HOME")
    if env:
        d = Path(env).expanduser()
    else:
        d = repo_root() or user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_dir() -> Path:
    return data_dir() / "browser_profile"


def output_dir() -> Path:
    return data_dir() / "output"


def history_file() -> Path:
    return data_dir() / "chat_history.txt"


def sites_file() -> Path:
    """sites.json 的实际位置（可能来自环境变量 / 仓库根 / 用户目录）。

    优先级:
      1. AI_CHAT_CLI_SITES  显式指定文件
      2. git clone 场景 → 仓库根的 sites.json（就是用户平时手改的那份）
      3. 用户目录（pip 安装场景；不存在时从包内默认配置复制一份）
    注意：设了 AI_CHAT_CLI_HOME 就视为"我已经指定了自己的 home"，
    此时跳过第 2 步，配置一律落在那个目录里（隔离测试靠这个）。
    """
    env = os.environ.get("AI_CHAT_CLI_SITES")
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            die(f"AI_CHAT_CLI_SITES 指向的文件不存在: {path}")
        return path

    if not os.environ.get("AI_CHAT_CLI_HOME"):
        root = repo_root()
        if root and (root / "sites.json").is_file():
            return root / "sites.json"

    target = user_config_dir() / "sites.json"
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BUNDLED_DIR / "sites.json", target)
        debug(f"已从内置默认配置生成 {target}")
    return target


def ensure_assets() -> None:
    """把包内资源（mock 页面等）铺到数据目录。

    仓库模式下数据目录就是仓库根，文件已存在，不会重复复制。
    """
    target_dir = data_dir()
    for name in BUNDLED_ASSETS:
        src = BUNDLED_DIR / name
        dst = target_dir / name
        if src.is_file() and not dst.exists():
            try:
                shutil.copyfile(src, dst)
            except OSError as e:  # 只读目录等
                debug(f"跳过复制 {name}: {e}")


def headless_default() -> bool:
    return os.environ.get("AI_CHAT_CLI_HEADLESS", "").strip() not in ("", "0", "false", "False")


# ---------------- 配置读取 ----------------


def load_sites(force: bool = False) -> dict:
    """读取并缓存 sites.json；出错给出人话提示而不是 traceback。"""
    global _sites_cache
    if _sites_cache is not None and not force:
        return _sites_cache

    path = sites_file()
    if not path.is_file():
        die(f"找不到站点配置文件: {path}\n可用环境变量 AI_CHAT_CLI_SITES 指定其他位置。")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"sites.json 格式有误（{path} 第 {e.lineno} 行）: {e.msg}")
    if not isinstance(data, dict) or not data:
        die(f"sites.json 内容不是一个有效的站点字典: {path}")

    _sites_cache = data
    debug(f"站点配置: {path}（{len(data)} 个站点）")
    return data


def known_sites() -> str:
    """ "doubao, deepseek, ... | all" 这样的提示文本。"""
    return f"{', '.join(load_sites())} | all"


def resolve_site_arg(value: str, sites: dict) -> list[str]:
    """把 <站点|all> 解析成站点 key 列表，非法就按"用法错误"退出（退出码 2）。"""
    if value == "all":
        return list(sites)
    if value in sites:
        return [value]
    die(f"未知站点: {value}，可用: {known_sites()}", EXIT_USAGE)
