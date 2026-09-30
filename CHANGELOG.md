# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0] - 2026-09-30

首个正式发布版本：五个网页 AI 站点可用，命令行输出契约稳定，可被脚本可靠调用。

### 新增

- **五个站点适配**：豆包 / DeepSeek / 通义千问 / 腾讯元宝 / Kimi，外加一个本地 `mock` 站点用于自测。
- **四个子命令**：`login`（打开浏览器手动登录）、`sites`（查看配置）、`chat`（单次问答 / 交互聊天）、
  `batch`（从 TXT 批量提问并归档）。
- **可安装包**：`pyproject.toml` + `[project.scripts]`，`pipx install ai-chat-cli` 之后
  直接敲 `ai-chat-cli chat doubao "问题"`，不必 clone 仓库。
- **配置文件自动落位**：装了包之后，配置放在用户目录
  （Windows `%APPDATA%\ai-chat-cli\`，其他 `~/.config/ai-chat-cli/`），
  首次运行从包内默认配置复制一份；`git clone` 用户的仓库根 `sites.json` 行为不变。
- **无 Edge 自动退回 Chromium**：`channel=msedge` 启动失败时自动改用 Playwright 自带的
  Chromium，macOS / Linux 用户不必再手改配置。
- **新命令行参数**：
  - `-q/--quiet`、`-v/--verbose`（子命令前后都能写）
  - `--dry-run`：先看"会问哪些问题、开哪些站点"，不启动浏览器
  - `--delay SEC`：批量提问的间隔，降低触发风控的概率
  - `chat/batch <site> -`：从管道读提示词，`cat questions.txt | ai-chat-cli chat doubao -`
  - `--print-completion bash|zsh|tcsh`：生成 shell 补全脚本（需 `shtab`）
- **自动化测试**：31 个 pytest 用例。25 个不依赖浏览器的 CLI 测试 + 6 个用 `mock` 站点的端到端测试，
  覆盖 stdout/stderr 分离、退出码、`--dry-run`、管道输入、配置解析。
- **GitHub Actions CI**：lint（ruff）+ 多 Python 版本（3.10 / 3.12 / 3.13）跑全部测试 +
  构建 wheel 并验证装完能用。
- **开源标配**：`CHANGELOG.md`、`CONTRIBUTING.md`、`SECURITY.md`、issue / PR 模板。

### 变更

- **代码拆分为包**：原来的单文件 `main.py`（约 500 行）拆成
  `ai_chat_cli/{console,config,browser,cli,devtools}.py`。
  根目录的 `main.py`、`login_keep.py`、`kill_stale.py`、`clean_cache.py`、
  `inspect_site.py`、`probe_send.py` 都保留为薄壳，**原有命令照旧可用**。
- **路径解析统一**：不再到处 `Path(__file__).parent / "sites.json"`，
  全部走 `ai_chat_cli/config.py`，这是能用 pip 安装的前提。
- **退出码修正**：未知站点名以前退出码是 `1`，现在按"用法错误"返回 `2`，
  与 README 里的表格一致。
- `requirements.txt` 加上版本上限：`playwright>=1.40,<2`，
  避免 Playwright 大版本变更时悄悄弄坏工具。

### 修复

- 错误提示以前用裸 `print()` 写进 stdout，会污染重定向的内容；现在统一走 stderr。
- 站点内容/回复抓不到时，`sites.json` 缺失或格式错误会直接抛 `Traceback`；现在给的是
  带行号的人话提示。

[Unreleased]: https://github.com/gyaoshi/ai-chat-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gyaoshi/ai-chat-cli/releases/tag/v0.1.0
