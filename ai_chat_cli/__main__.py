# -*- coding: utf-8 -*-
"""`python -m ai_chat_cli` 的入口，等价于 `ai-chat-cli` 命令。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
