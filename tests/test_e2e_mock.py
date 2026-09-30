# -*- coding: utf-8 -*-
"""端到端测试：用内置的 mock 站点跑完整链路（不需要任何账号）。

mock 站点是仓库自带的本地 HTML 页面（ai_chat_cli/data/test_mock.html），
它会逐字输出一段固定文本 —— 正好用来验证"发送 → 等流式结束 → 取回复"整条路。

默认无界面运行。CI（Linux）上加 AI_CHAT_CLI_CHANNEL=chromium：
    AI_CHAT_CLI_HEADLESS=1 AI_CHAT_CLI_CHANNEL=chromium pytest -m e2e
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import run_cli
from test_cli import MOCK_REPLY_TEMPLATE

pytestmark = pytest.mark.e2e


def test_chat_mock_returns_clean_stdout(e2e_env, isolated_home: Path):
    """最关键的一条：stdout 必须**只有**回复正文，一个字符都不多。"""
    r = run_cli("chat", "mock", "测试一下", env=e2e_env)
    assert r.returncode == 0
    assert r.stdout.strip() == MOCK_REPLY_TEMPLATE.format(msg="测试一下", n=1)
    # 进度信息必须都在 stderr
    assert "发送中" in r.stderr
    assert "Mock测试" not in r.stdout


def test_chat_mock_json_is_parsable(e2e_env):
    r = run_cli("chat", "mock", "第二条", "--json", env=e2e_env)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert isinstance(payload, list) and len(payload) == 1
    record = payload[0]
    assert record["site"] == "mock"
    assert record["message"] == "第二条"
    assert record["error"] is None
    assert record["reply"]
    assert record["seconds"] >= 0
    # JSON 模式下 stdout 必须是合法 JSON，不能混进日志
    assert "发送中" not in r.stdout


def test_chat_mock_writes_out_file(e2e_env, tmp_path: Path):
    target = tmp_path / "answer.txt"
    r = run_cli("chat", "mock", "写文件", "--out", str(target), env=e2e_env)
    assert r.returncode == 0
    assert target.is_file()
    assert "写文件" in target.read_text(encoding="utf-8")


def test_batch_mock_archives_every_prompt(e2e_env, isolated_home: Path, tmp_path: Path):
    prompts = tmp_path / "prompts.txt"
    prompts.write_text("# 这是注释\n问题一\n\n问题二\n", encoding="utf-8")

    r = run_cli("batch", "mock", str(prompts), env=e2e_env)
    assert r.returncode == 0

    # 归档结构: <home>/output/<时间戳>/mock/001.txt ...
    runs = list((isolated_home / "output").iterdir())
    assert len(runs) == 1
    site_dir = runs[0] / "mock"
    assert (site_dir / "001.txt").is_file()
    assert (site_dir / "002.txt").is_file()
    assert "问题一" in (site_dir / "001.txt").read_text(encoding="utf-8")

    summary = json.loads((runs[0] / "summary.json").read_text(encoding="utf-8"))
    assert [row["message"] for row in summary] == ["问题一", "问题二"]
    assert all(row["reply"] for row in summary)


def test_chat_message_from_pipe(e2e_env):
    """`cat questions.txt | ai-chat-cli chat doubao -` 这条 Unix 味儿用法的核心链路。"""
    r = run_cli("chat", "mock", "-", stdin="管道里的问题", env=e2e_env)
    assert r.returncode == 0
    assert "管道里的问题" in r.stdout


def test_mock_site_assets_are_materialised(e2e_env, isolated_home: Path):
    """独立 home 首次运行时，随包的 mock 页面应当被复制过去。"""
    r = run_cli("chat", "mock", "资源检查", env=e2e_env)
    assert r.returncode == 0
    assert (isolated_home / "test_mock.html").is_file()
    assert (isolated_home / "sites.json").is_file()
