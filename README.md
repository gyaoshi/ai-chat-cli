# ai-chat-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

用命令行驱动浏览器里的网页版 AI —— 同一个问题一次发给豆包、DeepSeek、通义千问、腾讯元宝、Kimi，
把回复原样收回来。也可以从 TXT 批量提问、自动归档结果，方便接进你自己的脚本流水线。

Drive the web AIs you already use — **Doubao, DeepSeek, Qwen (Tongyi), Tencent Yuanbao, Kimi** —
from your terminal. Send one question to all of them at once, get every answer back as plain text,
and batch-process a whole TXT file into organized output folders.

> **中文** · [English](#english)

---

## 中文

### 这是什么

不调用任何官方 API，也不做逆向接口。它用 Playwright 开一个**真实的、可见的 Edge 窗口**，
像人一样在网页里输入框打字、点发送、等流式回复读完，再把最后的回答交给你。
好处是：用的就是你自己登录的账号，能力、额度、联网搜索等你平时用什么就还是什么。

### 特性

- **五个平台开箱可用**：豆包 / DeepSeek / 通义千问 / 腾讯元宝 / Kimi，实测通过（2026-09）
- **可见浏览器 + 登录态持久化**：登录一次存进本地 profile，之后免登录
- **一条消息发给全部**：`chat all "问题"` 五个 AI 同时作答并汇总
- **交互聊天模式**：像聊天室一样连续对话
- **TXT 批量处理**：每行一条提示词，回复按 `output/时间戳/站点/序号.txt` 归档
- **脚本友好**：回复正文走 stdout，进度信息走 stderr；另有 `--json` / `--out`
- **抗改版**：站点选择器全在 `sites.json`，网页改版只改配置不改代码
- **自愈能力**：元素失效自动重找、检测到人机验证自动暂停等你处理、只在没拿到回复时才重发

### 安装

需要 **Python 3.10+**（Windows 上还需本机 Edge，Win10/11 自带）。
不需要下载 Playwright 自带的 Chromium —— 直接复用系统 Edge。

```bat
git clone https://github.com/gyaoshi/ai-chat-cli.git
cd ai-chat-cli
pip install -r requirements.txt
```

`requirements.txt` 里只有一行：`playwright`。

### 快速开始

```bat
:: 1. 打开浏览器登录（窗口保留 1 小时，慢慢登，登完关掉窗口即可）
login.bat

:: 2. 先自测一把（本地模拟页面，不需要账号）
ai.bat chat mock "测试"

:: 3. 正式使用
ai.bat chat doubao "帮我写一首关于秋天的五言绝句"
ai.bat chat all "解释一下什么是贝叶斯定理"
ai.bat batch all prompts.txt
```

> PowerShell 用户注意：PowerShell 不搜索当前目录，需要写成 `.\ai.bat sites`。
> CMD 里则可以直接 `ai.bat sites`。

### 平台与命令

命令格式统一为 `ai.bat chat <站点名> "你的问题"`：

| 平台 | 站点名 | 命令 | 登录要求 |
|------|--------|------|----------|
| 豆包 | `doubao` | `ai.bat chat doubao "问题"` | 需登录（偶发人机验证，程序会暂停等你处理） |
| DeepSeek | `deepseek` | `ai.bat chat deepseek "问题"` | 需登录 |
| 通义千问 | `tongyi` | `ai.bat chat tongyi "问题"` | 免登录 |
| 腾讯元宝 | `yuanbao` | `ai.bat chat yuanbao "问题"` | 需微信扫码 |
| Kimi | `kimi` | `ai.bat chat kimi "问题"` | 需手机号 / 微信 |
| 一次性问全部 | `all` | `ai.bat chat all "问题"` | 各平台各自要求 |
| 自测用 | `mock` | `ai.bat chat mock "测试"` | 免登录，本地模拟页 |

随时用 `ai.bat sites` 查看当前配置。不带问题就进交互模式：`ai.bat chat kimi`（`q` 退出）。

### 命令行参数

```
ai.bat login [站点...]                打开浏览器手动登录
ai.bat sites                          查看已配置站点
ai.bat chat <站点|all> [问题] [--json] [--out FILE]
ai.bat batch <站点|all> <TXT> [--json] [--out FILE]
login.bat [站点...] [--minutes N] [--forever]   登录专用，窗口保留更久
```

### 输出约定（写脚本必读）

**回复正文只从 stdout 输出；站点名、耗时、进度提示全部走 stderr。**
所以重定向拿到的就是干净内容，不用做字符串清洗：

```bat
:: 直接存文件
ai.bat chat doubao "写一句话" > answer.txt

:: 结构化输出
ai.bat chat all --json "总结博弈论" > result.json
ai.bat chat deepseek --json --out r.json "问题"
```

`--json` 每条记录的字段：`site`（站点名）、`name`（中文名）、`message`（提问）、
`reply`（回复，失败为 `null`）、`seconds`（耗时秒）、`error`（错误信息或 `null`）。

Python 里调用：

```python
import json, subprocess

out = subprocess.run(["ai.bat", "chat", "doubao", "--json", "你好"],
                     capture_output=True, text=True, encoding="utf-8")
reply = json.loads(out.stdout)[0]["reply"]
```

批处理除了逐条存档，还会生成 `output/<时间戳>/summary.json` 汇总所有问答。

### 配置站点（sites.json）

```jsonc
{
  "doubao": {
    "name": "豆包",
    "url": "https://www.doubao.com/chat/",
    "channel": "msedge",                 // 也可改成 "chromium"
    "input_selectors": ["div.tiptap.ProseMirror[contenteditable='true']"],
    "send_method": "button",             // "enter" 或 "button"
    "send_button_selectors": ["[data-testid='chat_input_send_button']"],
    "reply_selectors": ["[data-testid='receive_message'] [data-testid='message_text_content']"],
    "sent_marker_selectors": ["[data-testid='message_text_content']"],
    "placeholder_texts": [],             // 站点把提示语写进 DOM 时填这里
    "load_wait": 6,
    "stable_seconds": 3,                 // 文本连续 N 秒不变即认为回复结束
    "reply_timeout": 300
  }
}
```

字段速查：

| 字段 | 作用 |
|------|------|
| `input_selectors` | 输入框，按顺序试，取第一个可见的 |
| `send_method` | `enter` 回车发送；`button` 点发送按钮（编辑器类页面更可靠） |
| `reply_selectors` | 回复容器，取最后一个元素作为最新回复 |
| `sent_marker_selectors` | 对话消息节点，数量 +1 说明发送成功（适发送后不清空输入框的站点） |
| `placeholder_texts` | 站点把"请输入…"写进 DOM 时，填进来避免被误判成"还没发出去" |
| `stable_seconds` | 流式回复的结束判定阈值 |

### 换到其他电脑

依赖只有 `playwright` 一个包，浏览器用系统 Edge，把项目文件夹拷过去再 `pip install -r requirements.txt` 即可。
**不要拷贝 `browser_profile/`**（那是含 cookie 的登录数据），在新机器上重新 `login.bat` 一次更安全。

没有 Edge 的机器：先 `playwright install chromium`，再把 `sites.json` 里的 `channel` 改成 `"chromium"`。

### 常见故障

| 现象 | 处理 |
|------|------|
| 启动报乱码 / "已在另一个会话中打开" | 残留 Edge 占着 profile，运行 `python kill_stale.py` 后重试 |
| 找不到输入框、卡住不动 | 该站需重新登录（`login.bat`），或网页改版需更新选择器 |
| 抓到思考过程而不是答案 | 调整 `reply_selectors`，排除思维链容器（如 Kimi 的 `.toolcall-content-text`） |
| 弹出人机验证 | 程序自动暂停，在窗口里手动完成验证后自动继续 |
| 日志出现"未能确认消息已发出" | 发送判据不够准，补 `sent_marker_selectors` / `placeholder_texts` |
| `browser_profile\` 越用越大（几百 MB） | 都是可再生的浏览器缓存，运行 `python clean_cache.py` 清理，**登录状态不受影响** |

### 项目结构

```
main.py                  主程序（login / sites / chat / batch）
sites.json               站点配置
ai.bat / login.bat       启动器（自动寻找 Python 解释器）
login_keep.py            登录窗口（窗口保留 N 分钟，关窗即保存）
kill_stale.py            清理占用 browser_profile 的残留 Edge 进程
clean_cache.py           只清浏览器缓存、保留登录状态（profile 变大时用）
inspect_site.py          抓页面 DOM 结构 + 截图（网页改版时用）
probe_send.py            实发一条消息验证选择器（同时 dump 回复 DOM 到 test_report/）
test_mock.html           本地模拟 AI 页面（自测用）
requirements.txt         playwright
```

### 免责声明

本项目仅用于**个人学习与研究**，通过浏览器自动化操作你自己已登录的网页账号。
请遵守各平台的服务条款与 robots 协议，控制请求频率，不要用于批量爬取、商业倒卖或任何违法用途。
使用者需自行承担使用风险，作者不对账号受限、数据丢失等后果负责。

---

## English

### What it is

No official APIs, no reverse-engineered endpoints. This tool launches a **real, visible Edge window**
via Playwright and behaves like a human: it types into the chat box, clicks send, waits for the
streaming answer to finish, and hands you the final text. You keep using your own logged-in
accounts, so quotas, tools and web-search behave exactly as they normally do.

### Features

- **Five platforms out of the box**: Doubao, DeepSeek, Qwen (Tongyi), Tencent Yuanbao, Kimi — all verified (2026-09)
- **Visible browser + persistent login**: log in once, the profile is reused afterwards
- **One question, all AIs**: `chat all "question"` fans out and collects every answer
- **Interactive chat mode**: keep a conversation going like a chat room
- **Batch from a TXT file**: one prompt per line, answers archived as `output/<timestamp>/<site>/NNN.txt`
- **Script-friendly**: reply text on stdout, progress on stderr, plus `--json` / `--out`
- **Redesign-proof**: every selector lives in `sites.json` — site changes need config edits, not code edits
- **Self-healing**: re-locates detached elements, pauses for CAPTCHA so you can solve it, and only re-sends when no reply arrived

### Install

Requires **Python 3.10+** (plus Microsoft Edge on Windows — bundled with Win10/11).
Playwright's own Chromium download is **not** needed; the system Edge is reused.

```bat
git clone https://github.com/gyaoshi/ai-chat-cli.git
cd ai-chat-cli
pip install -r requirements.txt
```

`requirements.txt` contains exactly one line: `playwright`.

### Quick start

```bat
:: 1. Open a browser and log in (the window stays open for an hour)
login.bat

:: 2. Smoke test against a local mock page (no account needed)
ai.bat chat mock "test"

:: 3. Real usage
ai.bat chat doubao "Write a haiku about autumn"
ai.bat chat all "Explain Bayes' theorem"
ai.bat batch all prompts.txt
```

> PowerShell users: PowerShell does not search the current directory, so use `.\ai.bat sites`.
> In CMD, `ai.bat sites` works as-is.

### Platforms and commands

The command format is always `ai.bat chat <site> "your question"`:

| Platform | Site key | Command | Login required |
|----------|----------|---------|----------------|
| Doubao | `doubao` | `ai.bat chat doubao "q"` | Yes (occasional CAPTCHA — the tool pauses for you) |
| DeepSeek | `deepseek` | `ai.bat chat deepseek "q"` | Yes |
| Qwen (Tongyi) | `tongyi` | `ai.bat chat tongyi "q"` | No |
| Tencent Yuanbao | `yuanbao` | `ai.bat chat yuanbao "q"` | WeChat QR scan |
| Kimi | `kimi` | `ai.bat chat kimi "q"` | Phone number / WeChat |
| All at once | `all` | `ai.bat chat all "q"` | Each platform's own rules |
| Smoke test | `mock` | `ai.bat chat mock "test"` | No, local mock page |

Run `ai.bat sites` anytime to list what is configured. Omit the question to enter interactive
mode: `ai.bat chat kimi` (type `q` to quit).

### CLI reference

```
ai.bat login [site...]                open a browser and log in manually
ai.bat sites                          list configured sites
ai.bat chat <site|all> [question] [--json] [--out FILE]
ai.bat batch <site|all> <TXT> [--json] [--out FILE]
login.bat [site...] [--minutes N] [--forever]   login-only, keeps the window longer
```

### Output contract (read this before scripting)

**Reply text goes to stdout only; site names, timing and progress go to stderr.**
So redirected output is clean and needs no string scrubbing:

```bat
:: Save the answer directly
ai.bat chat doubao "say hi" > answer.txt

:: Structured output
ai.bat chat all --json "summarize game theory" > result.json
ai.bat chat deepseek --json --out r.json "question"
```

Each `--json` record contains: `site`, `name`, `message`, `reply` (`null` on failure),
`seconds`, `error`.

Calling it from Python:

```python
import json, subprocess

out = subprocess.run(["ai.bat", "chat", "doubao", "--json", "hello"],
                     capture_output=True, text=True, encoding="utf-8")
reply = json.loads(out.stdout)[0]["reply"]
```

Batch mode also writes `output/<timestamp>/summary.json` summarizing every Q&A pair.

### Configuring a site (sites.json)

```jsonc
{
  "doubao": {
    "name": "Doubao",
    "url": "https://www.doubao.com/chat/",
    "channel": "msedge",                 // or "chromium"
    "input_selectors": ["div.tiptap.ProseMirror[contenteditable='true']"],
    "send_method": "button",             // "enter" or "button"
    "send_button_selectors": ["[data-testid='chat_input_send_button']"],
    "reply_selectors": ["[data-testid='receive_message'] [data-testid='message_text_content']"],
    "sent_marker_selectors": ["[data-testid='message_text_content']"],
    "placeholder_texts": [],             // fill in if the site writes its hint text into the DOM
    "load_wait": 6,
    "stable_seconds": 3,                 // text unchanged for N seconds => reply finished
    "reply_timeout": 300
  }
}
```

| Field | Purpose |
|-------|---------|
| `input_selectors` | The chat box; tried in order, first visible one wins |
| `send_method` | `enter` = press Enter; `button` = click the send button (more reliable on rich-text editors) |
| `reply_selectors` | Answer containers; the last element is treated as the newest reply |
| `sent_marker_selectors` | Conversation nodes; count +1 means the message was posted (for sites that don't clear the input) |
| `placeholder_texts` | For sites that render their hint text as real DOM text — prevents false "not sent" detection |
| `stable_seconds` | Streaming-end threshold |

### Moving to another machine

The only dependency is the `playwright` package; the browser is your system Edge.
Copy the folder and run `pip install -r requirements.txt`.
**Do not copy `browser_profile/`** — it holds cookies. Log in again with `login.bat` on the new machine.

No Edge installed? Run `playwright install chromium` and set `channel` to `"chromium"` in `sites.json`.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Garbled launch error / "opened in another session" | A stale Edge holds the profile — run `python kill_stale.py` and retry |
| `browser_profile\` grows to hundreds of MB | All disposable browser cache — run `python clean_cache.py`; logins are kept |
| Input box never appears | Log in again (`login.bat`), or the site was redesigned and selectors need updating |
| You get the chain-of-thought instead of the answer | Adjust `reply_selectors` to exclude the reasoning container (e.g. Kimi's `.toolcall-content-text`) |
| CAPTCHA appears | The tool pauses automatically; solve it in the window and it continues |
| Log says "could not confirm the message was sent" | Send detection is imperfect — add `sent_marker_selectors` / `placeholder_texts` |

### Project layout

```
main.py                  entry point (login / sites / chat / batch)
sites.json               site configuration
ai.bat / login.bat       Windows launchers (auto-detect the Python interpreter)
login_keep.py            login window (stays open N minutes, saves on close)
kill_stale.py            kill leftover Edge processes holding browser_profile
clean_cache.py           trim browser caches only, keep logins (when profile grows big)
inspect_site.py          dump a site's DOM structure + screenshot (for redesigns)
probe_send.py            send one real message to verify selectors (also dumps reply DOM to test_report/)
test_mock.html           local mock AI page for self-testing
requirements.txt         playwright
```

### Disclaimer

This project is intended for **personal learning and research only**, driving a browser against
accounts you are already logged into. Please comply with each platform's terms of service and
robots policy, keep request rates low, and do not use it for bulk scraping, resale, or anything
unlawful. Use at your own risk; the author is not liable for account restrictions or data loss.

### License

[MIT](LICENSE) © 2026 gyaoshi
