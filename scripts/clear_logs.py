#!/usr/bin/env python3
"""
日志清理脚本

- 默认读取 config/settings.json 的 system.log_dir 与 system.cleanup_days
- 支持按天和按大小阈值清理 .log 文件
- 提供 --dry-run 进行模拟执行，便于安全检查

用法示例：
  conda run -n video_rewrite_env_py312 python -u scripts/clear_logs.py --dry-run
  conda run -n video_rewrite_env_py312 python -u scripts/clear_logs.py --days 7 --max-size-mb 50
"""

import argparse
import os
import sys
import time
from pathlib import Path


def _project_src_path() -> Path:
    # 此脚本位于 scripts/，src 在上一层
    return Path(__file__).resolve().parents[1] / "src"


def load_config():
    # 将 src 加入搜索路径以便导入 modules
    src_path = _project_src_path()
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    try:
        from modules.config import get_config  # noqa
        return get_config()
    except Exception as e:
        print(f"无法加载配置模块，改用默认设置。原因: {e}")
        class Dummy:
            def get(self, key, default=None):
                return default
        return Dummy()


def human_size(bytes_count: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} TB"


def clear_logs(log_dir: Path, days: int, max_size_mb: float | None, dry_run: bool) -> dict:
    now = time.time()
    cutoff = now - days * 24 * 60 * 60
    removed = []
    skipped = []
    freed_bytes = 0

    if not log_dir.exists():
        return {"removed": removed, "skipped": skipped, "freed_bytes": freed_bytes, "log_dir": str(log_dir)}

    for p in log_dir.glob("*.log"):
        try:
            stat = p.stat()
            size_ok = True
            time_ok = True

            # 按大小阈值
            if max_size_mb is not None:
                size_ok = stat.st_size >= int(max_size_mb * 1024 * 1024)

            # 按时间阈值
            time_ok = stat.st_mtime <= cutoff

            if size_ok or time_ok:
                if dry_run:
                    print(f"[DRY-RUN] 删除 {p.name} | 大小 {human_size(stat.st_size)} | 修改时间 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))}")
                else:
                    freed_bytes += stat.st_size
                    p.unlink(missing_ok=True)
                    removed.append(p.name)
            else:
                skipped.append(p.name)
        except Exception as e:
            print(f"跳过 {p}: {e}")

    return {"removed": removed, "skipped": skipped, "freed_bytes": freed_bytes, "log_dir": str(log_dir)}


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="清理日志文件")
    parser.add_argument("--log-dir", default=cfg.get("system.log_dir", "logs"), help="日志目录")
    parser.add_argument("--days", type=int, default=cfg.get("system.cleanup_days", 7), help="清理超过 N 天的日志")
    parser.add_argument("--max-size-mb", type=float, default=None, help="清理大于指定大小的日志（可选）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要删除的文件，不实际删除")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    result = clear_logs(log_dir, args.days, args.max_size_mb, args.dry_run)

    print("-" * 60)
    print(f"日志目录: {result['log_dir']}")
    print(f"删除数量: {len(result['removed'])}")
    print(f"保留数量: {len(result['skipped'])}")
    print(f"释放空间: {human_size(result['freed_bytes'])}")
    if args.dry_run:
        print("说明: DRY-RUN 模式未实际删除文件")


if __name__ == "__main__":
    main()