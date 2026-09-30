# -*- coding: utf-8 -*-
"""只清理 browser_profile 里可再生的浏览器缓存，保留全部登录状态。

长时间使用后 browser_profile 会膨胀到几百 MB（Cache / Code Cache / 遥测数据），
本脚本把这些删掉，只留下 cookies、Local Storage、IndexedDB 等登录凭据，因此
**不需要重新登录**。

用法:
    python clean_cache.py            # 清理并报告释放空间
    python clean_cache.py --dry-run  # 只查看哪些目录占空间，不删
"""
import argparse
import shutil
import stat
import sys
from pathlib import Path

from kill_stale import kill_stale

BASE = Path(__file__).parent
PROFILE = BASE / "browser_profile"

# 可安全删除的缓存/遥测目录或文件（相对 browser_profile）
CACHE_TARGETS = [
    "BrowserMetrics",
    "DeferredBrowserMetrics",
    "GrShaderCache",
    "ShaderCache",
    "GraphiteDawnCache",
    "GPUPersistentCache",
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/DawnWebGPUCache",
    "Default/DawnGraphiteCache",
    "Default/Service Worker/CacheStorage",
    "Default/load_statistics.db",
    "Default/settings_diagnostic.log",
    "Default/favorites_diagnostic.log",
]


def dir_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def force_rm(func, path, exc):
    try:
        import os
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"    跳过 {path}: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="清理 browser_profile 缓存（保留登录状态）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不删除")
    args = ap.parse_args()

    if not PROFILE.exists():
        print("browser_profile/ 不存在，无需清理。")
        return

    total = dir_size(PROFILE)
    print(f"当前 browser_profile 体积: {total / 1024 / 1024:.1f} MB")

    if not args.dry_run:
        n = kill_stale()
        print(f"已结束占用 profile 的 Edge 进程数: {n}")

    freed = 0
    print("\n缓存项:")
    for rel in CACHE_TARGETS:
        p = PROFILE / rel
        if not p.exists():
            continue
        sz = dir_size(p)
        freed += sz
        tag = "（将删除）" if not args.dry_run else ""
        print(f"  {sz / 1024 / 1024:>8.1f} MB  {rel}{tag}")
        if not args.dry_run:
            if p.is_file():
                p.unlink(missing_ok=True)
            else:
                shutil.rmtree(p, onerror=force_rm)

    keep = sorted(
        k for k in ["Default/Network/Cookies", "Default/Local Storage", "Default/IndexedDB",
                    "Default/Session Storage", "Default/Login Data", "Default/Preferences",
                    "Local State"]
        if (PROFILE / k).exists()
    )
    print("\n保留的登录凭据:")
    for k in keep:
        print(f"  {k}")

    if args.dry_run:
        print(f"\n[dry-run] 可释放约 {freed / 1024 / 1024:.1f} MB，加 --dry-run 之外的参数即执行删除。")
    else:
        after = dir_size(PROFILE)
        print(f"\n清理完成：释放 {freed / 1024 / 1024:.1f} MB，"
              f"现在 {after / 1024 / 1024:.1f} MB。登录状态保持不变。")


if __name__ == "__main__":
    main()
