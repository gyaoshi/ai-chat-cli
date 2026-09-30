#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容入口（薄壳）。真正实现在 ai_chat_cli/ 包里。

以前的所有文档都写 `python main.py ...`，这里保持完全可用。
装了包之后也可以直接敲 `ai-chat-cli ...`，或用 `python -m ai_chat_cli ...`。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.cli import main

if __name__ == "__main__":
    sys.exit(main())
