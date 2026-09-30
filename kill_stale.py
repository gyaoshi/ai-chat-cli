# -*- coding: utf-8 -*-
"""清理占用 browser_profile 的残留 Edge 进程（上次异常退出没关干净时用）

用法: python kill_stale.py
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
PROFILE = str(BASE / "browser_profile")


def kill_stale():
    """结束所有使用本项目 browser_profile 的 Edge 进程，返回结束数量（失败返回 None）"""
    ps = (
        "$procs = Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{PROFILE.replace(chr(92), chr(92)*2)}*' }}; "
        "$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "Write-Output $procs.Count"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    lines = (r.stdout or "").strip().splitlines()
    n = lines[-1] if lines else None
    if r.returncode != 0:
        print("PowerShell 报错:", r.stderr, file=sys.stderr)
    return n


if __name__ == "__main__":
    print(f"已结束占用 browser_profile 的 Edge 进程数: {kill_stale()}", flush=True)
