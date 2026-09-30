#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清理 browser_profile 缓存、保留登录状态（薄壳）。实现在 ai_chat_cli/devtools.py。

用法:
    python clean_cache.py            清理并报告释放空间
    python clean_cache.py --dry-run  只查看哪些目录占空间，不删
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.devtools import main_clean_cache

if __name__ == "__main__":
    sys.exit(main_clean_cache())
