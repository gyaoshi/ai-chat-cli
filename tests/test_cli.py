# -*- coding: utf-8 -*-
"""不依赖浏览器的冒烟测试：参数、退出码、stdout/stderr 契约、配置解析。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import PKG_DATA, ROOT, run_cli

MOCK_REPLY_TEMPLATE = (
    "收到你的消息「{msg}」。这是模拟AI的第{n}条回复，"
    "用于自动化测试验证发送与流式回复捕获是否正常工作，"
    "内容足够长以模拟真实的逐字输出效果。"
)


# ---------------- 版本 / 帮助 ----------------


def test_version():
    r = run_cli("--version")
    assert r.returncode == 0
    assert r.stdout.strip().startswith("ai-chat-cli ")


def test_help_lists_all_subcommands():
    r = run_cli("--help")
    assert r.returncode == 0
    for cmd in ("login", "sites", "chat", "batch"):
        assert cmd in r.stdout
    # 帮助里必须写明输出约定和退出码，否则用户不知道能拿去写脚本
    assert "stdout" in r.stdout
    assert "退出码" in r.stdout


def test_subcommand_help():
    r = run_cli("batch", "--help")
    assert r.returncode == 0
    assert "--dry-run" in r.stdout
    assert "--delay" in r.stdout


# ---------------- sites ----------------


def test_sites_lists_every_configured_site():
    r = run_cli("sites")
    assert r.returncode == 0
    keys = json.loads((ROOT / "sites.json").read_text(encoding="utf-8"))
    for key in keys:
        assert key in r.stdout
    # 配置文件路径属于装饰信息，必须走 stderr
    assert "sites.json" not in r.stdout
    assert "sites.json" in r.stderr


def test_quiet_silences_stderr_but_keeps_stdout():
    r = run_cli("-q", "sites")
    assert r.returncode == 0
    assert r.stdout.strip()
    assert r.stderr.strip() == ""


def test_quiet_works_after_subcommand_too():
    """`-q` 放子命令前后都必须认（两种写法都常在脚本里出现）。"""
    before = run_cli("-q", "sites")
    after = run_cli("sites", "-q")
    assert after.returncode == 0
    assert after.stdout == before.stdout
    assert after.stderr.strip() == ""


def test_verbose_adds_debug_lines():
    r = run_cli("sites", "-v")
    assert r.returncode == 0
    assert "[debug]" in r.stderr


# ---------------- shell 补全 ----------------


def test_print_completion_bash():
    pytest.importorskip("shtab")
    r = run_cli("--print-completion", "bash")
    assert r.returncode == 0
    assert "_ai-chat-cli" in r.stdout or "ai-chat-cli" in r.stdout
    assert "compdef" not in r.stdout


# ---------------- 退出码 ----------------


@pytest.mark.parametrize("site", ["bogus", "Doubao"])
def test_unknown_site_is_usage_error(site):
    r = run_cli("chat", site, "hi")
    assert r.returncode == 2
    assert r.stdout.strip() == ""  # 错误信息绝不能跑进 stdout
    assert "未知站点" in r.stderr


def test_missing_prompt_file_is_runtime_error():
    r = run_cli("batch", "mock", "no_such_file_12345.txt")
    assert r.returncode == 1
    assert r.stdout.strip() == ""
    assert "不存在" in r.stderr


def test_missing_config_file_is_friendly(monkeypatch, tmp_path: Path):
    missing = tmp_path / "nope.json"
    r = run_cli("sites", env={"AI_CHAT_CLI_SITES": str(missing)})
    assert r.returncode == 1
    assert "不存在" in r.stderr
    assert "Traceback" not in r.stderr


def test_broken_config_file_points_at_line(tmp_path: Path):
    bad = tmp_path / "sites.json"
    bad.write_text('{"a": 1,}', encoding="utf-8")  # 多一个逗号
    r = run_cli("sites", env={"AI_CHAT_CLI_SITES": str(bad)})
    assert r.returncode == 1
    assert "格式有误" in r.stderr
    assert "Traceback" not in r.stderr


def test_no_arguments_is_usage_error():
    r = run_cli()
    assert r.returncode == 2


# ---------------- --dry-run（不启动浏览器）----------------


def test_dry_run_chat_needs_no_browser():
    r = run_cli("chat", "doubao", "你好", "--dry-run")
    assert r.returncode == 0
    assert "doubao" in r.stdout
    assert "你好" in r.stdout
    assert "--dry-run" in r.stdout


def test_dry_run_batch_lists_prompts_and_skips_comments():
    r = run_cli("batch", "mock", "test_prompts.txt", "--dry-run")
    assert r.returncode == 0
    assert "你好，请用一句话介绍自己" in r.stdout
    # test_prompts.txt 第一行是 "# 注释行会被跳过"
    assert "注释行会被跳过" not in r.stdout


def test_dry_run_all_sites():
    r = run_cli("batch", "all", "test_prompts.txt", "--dry-run")
    assert r.returncode == 0
    assert "6 个站点" in r.stdout


def test_dry_run_chat_interactive_is_rejected():
    r = run_cli("chat", "mock", "--dry-run")
    assert r.returncode == 2
    assert "--dry-run" in r.stderr


# ---------------- 从管道读提示词 ----------------


def test_batch_reads_prompts_from_stdin():
    r = run_cli("batch", "mock", "-", "--dry-run", stdin="# 注释\n管道第一条\n管道第二条\n")
    assert r.returncode == 0
    assert "管道第一条" in r.stdout
    assert "管道第二条" in r.stdout
    assert "注释" not in r.stdout


def test_empty_stdin_is_runtime_error():
    r = run_cli("batch", "mock", "-", "--dry-run", stdin="\n\n")
    assert r.returncode == 1
    assert "没有可用的提示词" in r.stderr


# ---------------- 配置解析（pip 安装场景）----------------


def test_user_config_dir_is_used_when_no_repo(tmp_path: Path):
    """模拟 pipx 安装后的场景：仓库里找不到 sites.json，就用用户目录。"""
    home = tmp_path / "appdata"
    r = run_cli("sites", env={"AI_CHAT_CLI_HOME": str(home)})
    assert r.returncode == 0
    # 首次运行应当把内置默认配置复制出来
    copied = home / "sites.json"
    assert copied.is_file()
    assert json.loads(copied.read_text(encoding="utf-8"))


def test_env_override_wins(tmp_path: Path):
    custom = tmp_path / "custom.json"
    custom.write_text(
        json.dumps(
            {
                "mysite": {
                    "name": "我的站点",
                    "url": "https://example.com/",
                    "input_selectors": ["textarea"],
                }
            }
        ),
        encoding="utf-8",
    )
    r = run_cli("sites", env={"AI_CHAT_CLI_SITES": str(custom)})
    assert r.returncode == 0
    assert "mysite" in r.stdout
    assert "doubao" not in r.stdout


# ---------------- 包内资源与服务方式 ----------------


def test_bundled_data_is_in_sync_with_repo_files():
    """仓库根的 sites.json / test_mock.html 必须和包内自带的一致，否则 pip 用户会拿到旧配置。"""
    for name in ("sites.json", "test_mock.html", "test_prompts.txt"):
        assert (PKG_DATA / name).read_bytes() == (ROOT / name).read_bytes(), (
            f"{name} 与 ai_chat_cli/data/{name} 不一致，请同步"
        )


def test_main_py_shim_still_works():
    """所有旧文档都写 `python main.py`，这个兼容入口必须一直能跑。"""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "main.py", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0
    assert "ai-chat-cli" in r.stdout


def test_python_m_entrypoint_matches():
    r = run_cli("--version")
    assert r.returncode == 0
