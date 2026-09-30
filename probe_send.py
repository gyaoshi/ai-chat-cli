#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真发一条消息验证选择器（薄壳）。实现在 ai_chat_cli/devtools.py。

用法: python probe_send.py <站点...>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.devtools import main_probe_send

if __name__ == "__main__":
    sys.exit(main_probe_send(sys.argv[1:]))
