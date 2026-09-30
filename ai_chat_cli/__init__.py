# -*- coding: utf-8 -*-
"""ai-chat-cli —— 用命令行驱动浏览器里的网页版 AI。

包结构:
  console.py  日志级别与退出码（唯一的输出约定）
  config.py   路径与配置解析（唯一回答"配置在哪"的地方）
  browser.py  Playwright 页面操作（发送、等待、取回复）
  cli.py      命令行入口与子命令
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
