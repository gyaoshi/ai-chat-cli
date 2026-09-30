#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结束占用 browser_profile 的残留 Edge 进程（薄壳）。实现在 ai_chat_cli/devtools.py。

用法: python kill_stale.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.devtools import main_kill_stale

if __name__ == "__main__":
    sys.exit(main_kill_stale())
