#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""登录专用窗口（薄壳）。实现在 ai_chat_cli/devtools.py。

用法:
  python login_keep.py [站点...]          默认保留 60 分钟
  python login_keep.py --minutes 180      保留 180 分钟
  python login_keep.py --forever          不限时，直到你关掉窗口
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.devtools import main_login_window

if __name__ == "__main__":
    sys.exit(main_login_window())
