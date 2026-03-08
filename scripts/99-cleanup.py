#!/usr/bin/env python3
"""清理旧的运行目录和数据库过期记录"""

import os
import sys
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_config, load_db, save_db, DATA_DIR


def main():
    config = load_config()
    pipeline_cfg = config.get('pipeline', {}).get('history', {})
    days_to_keep = pipeline_cfg.get('daysToKeep', 7)
    cleanup_after_days = pipeline_cfg.get('cleanupAfterDays', 30)

    today = datetime.now().date()
    runs_dir = os.path.join(DATA_DIR, 'runs')

    # 清理旧运行目录
    deleted_dirs = 0
    if os.path.isdir(runs_dir):
        for name in sorted(os.listdir(runs_dir)):
            dir_path = os.path.join(runs_dir, name)
            if not os.path.isdir(dir_path):
                continue
            try:
                run_date = datetime.strptime(name, "%Y-%m-%d").date()
                age_days = (today - run_date).days
                if age_days > days_to_keep:
                    shutil.rmtree(dir_path)
                    deleted_dirs += 1
                    print(f"🗑️  删除运行目录: {name} ({age_days} 天前)")
            except ValueError:
                continue

    print(f"📁 清理运行目录: 删除 {deleted_dirs} 个 (保留 {days_to_keep} 天)")

    # 清理数据库中过期的文章记录
    db = load_db()
    cutoff = (today - timedelta(days=cleanup_after_days)).strftime("%Y-%m-%dT00:00:00Z")
    keys_to_remove = []

    for key, art in db.get("articles", {}).items():
        last_seen = art.get("lastSeen", art.get("firstSeen", ""))
        if last_seen and last_seen < cutoff:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del db["articles"][key]

    if keys_to_remove:
        save_db(db)

    print(f"📊 清理数据库: 删除 {len(keys_to_remove)} 条过期记录 (保留 {cleanup_after_days} 天)")
    print(f"📊 数据库剩余: {len(db.get('articles', {}))} 条记录")

    return 0


if __name__ == "__main__":
    sys.exit(main())
