# -*- coding: utf-8 -*-
"""清理占用 browser_profile 的残留 Edge 进程（上次异常退出没关干净时用）

用法: python kill_stale.py
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
PROFILE = str(BASE / "browser_profile")

ps = (
    "$procs = Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
    f"Where-Object {{ $_.CommandLine -like '*{PROFILE.replace(chr(92), chr(92)*2)}*' }}; "
    "$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
    "Write-Output $procs.Count"
)
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True)
count = (r.stdout or "").strip().splitlines()
n = count[-1] if count else "?"
print(f"已结束占用 browser_profile 的 Edge 进程数: {n}", flush=True)
if r.returncode != 0:
    print("PowerShell 报错:", r.stderr, file=sys.stderr)
