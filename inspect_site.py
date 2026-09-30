#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抓站点真实 DOM + 截图（薄壳）。实现在 ai_chat_cli/devtools.py。

用法: python inspect_site.py [站点...]     默认 tongyi yuanbao kimi
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_chat_cli.devtools import main_inspect_site

if __name__ == "__main__":
    sys.exit(main_inspect_site(sys.argv[1:]))
