# 贡献指南 / Contributing

先说结论：这个项目最需要的贡献是 **站点选择器更新**（网页一改版就失效）和 **新的站点适配**。
改代码前请先读完「输出契约」那一节 —— 它是这个工具能被脚本可靠调用的前提。

> **中文** · [English](#english)

## 开发环境

```bash
git clone https://github.com/gyaoshi/ai-chat-cli.git
cd ai-chat-cli

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[dev]"          # 装成可编辑模式，改代码立即生效
playwright install chromium      # 端到端测试需要一个无界面浏览器
```

跑测试：

```bash
pytest -m "not e2e" -q    # 快速：不启动浏览器，约 30 秒
pytest -q                 # 全部：含 mock 站点的端到端，约 2 分钟
ruff check . && ruff format --check .
```

端到端测试**不需要任何账号**：它用仓库自带的 `test_mock.html` 当站点，
验证「发送 → 等流式结束 → 取回复 → 写 stdout」整条链路。
CI 里靠两个环境变量切到无界面模式：

```bash
AI_CHAT_CLI_HEADLESS=1 AI_CHAT_CLI_CHANNEL=chromium pytest -m e2e
```

## 输出契约（改代码前必读）

| 通道 | 内容 |
|---|---|
| **stdout** | 只有回复正文；`--json` / `--dry-run` 时是结构化结果 |
| **stderr** | 进度、站点名、耗时、警告、错误 |

所有输出都必须经过 `ai_chat_cli/console.py`：

```python
from .console import log, warn, die, out

log("进度信息")  # → stderr
warn("警告")  # → stderr，-q 时也显示
out(reply)  # → stdout，唯一允许写内容的地方
die("致命错误", 1)  # → stderr + sys.exit(1)
```

**不要**用裸 `print()` 输出日志 —— 那会破坏 `ai-chat-cli chat doubao "问题" > answer.txt`。

退出码语义（改坏了脚本会静默出错）：

| 码 | 含义 |
|:--:|---|
| 0 | 全部成功 |
| 1 | 运行错误（配置缺失、文件不存在） |
| 2 | 用法错误（参数写错） |
| 3 | 至少一个站点没拿到回复 |

## 加一个新站点

1. **抓结构**。先打开浏览器登录一次，再跑：

   ```bash
   python inspect_site.py <站点key>       # 或者临时把新站点先写进 sites.json
   ```
   产物在 `test_report/<站点key>.{json,png}`：输入框、`contenteditable`、`data-testid` 一览。

2. **写配置**。往 `sites.json` 里加一段（字段说明见 README 的「配置站点」表）：

   ```json
   "newsite": {
     "name": "某站",
     "url": "https://example.com/chat/",
     "channel": "msedge",
     "input_selectors": ["textarea", "div[contenteditable='true']"],
     "reply_selectors": [".answer-markdown"],
     "sent_marker_selectors": ["div.message"],
     "send_method": "enter",
     "load_wait": 6,
     "stable_seconds": 3,
     "reply_timeout": 300
   }
   ```

3. **实发验证**：

   ```bash
   python probe_send.py newsite            # 真发一条消息，dump 回复 DOM 到 test_report/
   ai-chat-cli chat newsite "1+1等于几"
   ```

4. **同步包内副本**：`cp sites.json ai_chat_cli/data/sites.json`
   （有个测试会检查两者一致，否则 pip 用户拿到的还是旧配置）。

5. **跑测试**：`pytest -q && ruff check .`

### 选择器写不出来的常见情况

| 现象 | 处理办法 |
|---|---|
| 发送后输入框不清空 | 配 `sent_marker_selectors`：靠"消息节点数 +1"判断已发送 |
| 站点把提示语写进 DOM（如通义千问的"向千问提问"） | 把它填进 `placeholder_texts`，否则会被误判成"没发出去" |
| 抓到了思维链而不是答案 | 在 `reply_selectors` 里用 `:not(...)` 排掉推理容器（Kimi 的 `.toolcall-content-text` 就是这样） |
| 按钮发送更可靠（富文本编辑器） | `"send_method": "button"` + `send_button_selectors` |
| 回答很长、流式输出慢 | 调大 `stable_seconds` / `reply_timeout` |

## 代码风格

- `ruff check` + `ruff format`，行宽 100，目标 Python 3.10。提交前跑一遍，CI 会查。
- 注释和文档字符串用中文，说清**为什么**这么写，而不是重复代码在做什么。
- 新增的公共函数请加类型标注。

## 提交 PR

- 一个 PR 只做一件事。
- 说明里写清：改了什么、为什么、怎么验证的（附命令和输出更好）。
- 别提交 `browser_profile/`、`output/`、`test_report/`、`python_path.txt`。
  日志和截图里的账号、手机号、cookie 请先处理掉。

## 不要做的事

- 不要走逆向接口、不要伪造请求、不要绕过平台限制。这个工具刻意只做"浏览器替你打字"。
- 不要加入任何批量爬取、刷量、倒卖类功能。
- 不要为了"跑得快"默认开并发或缩短间隔 —— 风控是真实存在的，速度不该以牺牲账号为代价。

---

## English

Bottom line first: the contributions this project needs most are **selector updates** (sites
redesign and break them) and **new site adapters**. Read the "Output contract" section before
touching code — it is what makes this tool reliably callable from scripts.

### Development setup

```bash
git clone https://github.com/gyaoshi/ai-chat-cli.git
cd ai-chat-cli

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[dev]"          # editable install — code changes take effect immediately
playwright install chromium      # the e2e tests need a headless browser
```

Running the tests:

```bash
pytest -m "not e2e" -q    # fast: no browser, ~30 seconds
pytest -q                 # everything: includes the mock-site e2e, ~2 minutes
ruff check . && ruff format --check .
```

The e2e tests need **no account at all**: they use the repository's own `test_mock.html` as a site
and verify the whole path from *send → wait for streaming to finish → read the reply → write stdout*.
CI switches to headless mode through two environment variables:

```bash
AI_CHAT_CLI_HEADLESS=1 AI_CHAT_CLI_CHANNEL=chromium pytest -m e2e
```

### Output contract (read before changing code)

| Stream | Contents |
|---|---|
| **stdout** | reply text only; structured results under `--json` / `--dry-run` |
| **stderr** | progress, site names, timings, warnings, errors |

All output must go through `ai_chat_cli/console.py`:

```python
from .console import log, warn, die, out

log("progress info")  # → stderr
warn("warning")  # → stderr, still shown under -q
out(reply)  # → stdout — the only place allowed to write content
die("fatal error", 1)  # → stderr + sys.exit(1)
```

Do **not** use bare `print()` for logs — it would break
`ai-chat-cli chat doubao "question" > answer.txt`.

Exit-code semantics (breaking these makes scripts fail silently):

| Code | Meaning |
|:--:|---|
| 0 | everything succeeded |
| 1 | runtime error (missing config, file not found) |
| 2 | usage error (bad arguments) |
| 3 | at least one site returned no reply |

### Adding a new site

1. **Dump the structure.** Log in once in the browser, then run:

   ```bash
   python inspect_site.py <site-key>       # or temporarily add the new site to sites.json first
   ```
   Output lands in `test_report/<site-key>.{json,png}`: an overview of input boxes,
   `contenteditable` elements, and `data-testid` attributes.

2. **Write the config.** Add a block to `sites.json` (field descriptions are in the README's
   "configuring sites" table):

   ```json
   "newsite": {
     "name": "Some Site",
     "url": "https://example.com/chat/",
     "channel": "msedge",
     "input_selectors": ["textarea", "div[contenteditable='true']"],
     "reply_selectors": [".answer-markdown"],
     "sent_marker_selectors": ["div.message"],
     "send_method": "enter",
     "load_wait": 6,
     "stable_seconds": 3,
     "reply_timeout": 300
   }
   ```

3. **Verify with a real send**:

   ```bash
   python probe_send.py newsite            # sends one real message, dumps the reply DOM to test_report/
   ai-chat-cli chat newsite "what is 1+1"
   ```

4. **Sync the bundled copy**: `cp sites.json ai_chat_cli/data/sites.json`
   (a test asserts the two are identical, otherwise pip users keep getting the old config).

5. **Run the tests**: `pytest -q && ruff check .`

#### Common selector problems

| Symptom | Fix |
|---|---|
| The input box is not cleared after sending | Set `sent_marker_selectors` and detect "message node count +1" instead |
| The site writes its hint text into the DOM (e.g. Tongyi's "向千问提问") | List it in `placeholder_texts`, otherwise the send looks like it never happened |
| You captured the chain of thought instead of the answer | Exclude the reasoning container with `:not(...)` in `reply_selectors` (that is what Kimi's `.toolcall-content-text` needs) |
| A send button is more reliable (rich-text editors) | `"send_method": "button"` plus `send_button_selectors` |
| Very long answers, slow streaming | Increase `stable_seconds` / `reply_timeout` |

### Code style

- `ruff check` + `ruff format`, line width 100, target Python 3.10. Run both before committing —
  CI checks them.
- Comments and docstrings are written in Chinese; explain **why** the code is written this way
  rather than restating what it does.
- Add type hints to new public functions.

### Submitting a PR

- One PR, one thing.
- State what changed, why, and how you verified it (commands and output are welcome).
- Never commit `browser_profile/`, `output/`, `test_report/`, or `python_path.txt`.
  Strip accounts, phone numbers, and cookies from any logs or screenshots first.

### Things not to do

- No reverse-engineered APIs, no forged requests, no bypassing platform limits. This tool
  deliberately does exactly one thing: it types into a browser for you.
- Do not add bulk-scraping, engagement-farming, or resale features.
- Do not enable concurrency or shorten delays by default just to "go faster" — rate limiting is
  real, and speed must never come at the cost of someone's account.
