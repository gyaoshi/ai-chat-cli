# -*- coding: utf-8 -*-
"""pytest 公共夹具。

设计原则：所有测试都通过**真实的命令行进程**跑，而不是 import 后调函数。
这样测到的就是用户实际敲的那条命令（含 argparse、stdout/stderr 分离、退出码），
也顺带保证"从零 clone 下来能跑"这件事不会悄悄坏掉。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG_DATA = ROOT / "ai_chat_cli" / "data"


def run_cli(
    *args: str, stdin: str | None = None, env: dict | None = None, timeout: int = 300
) -> subprocess.CompletedProcess:
    """在仓库根目录下运行 `python -m ai_chat_cli <args>`。"""
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env.pop("AI_CHAT_CLI_HEADLESS", None)
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "ai_chat_cli", *args],
        cwd=ROOT,
        env=child_env,
        input=stdin,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture
def isolated_home(tmp_path: Path) -> Path:
    """独立的数据目录，避免测试污染真实 browser_profile / output。"""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def e2e_env(isolated_home: Path) -> dict:
    """端到端测试的环境：无界面 + 独立数据目录。"""
    env = {
        "AI_CHAT_CLI_HOME": str(isolated_home),
        "AI_CHAT_CLI_HEADLESS": os.environ.get("AI_CHAT_CLI_HEADLESS", "1"),
    }
    if os.environ.get("AI_CHAT_CLI_CHANNEL"):
        env["AI_CHAT_CLI_CHANNEL"] = os.environ["AI_CHAT_CLI_CHANNEL"]
    return env


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT
