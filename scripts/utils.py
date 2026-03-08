#!/usr/bin/env python3
"""共享工具模块 - 文章数据库、配置读取、运行目录管理"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone

# 动态获取项目根目录（基于脚本位置）
# 这样脚本可以在任何位置运行，包括本地和 GitHub Actions
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)  # 向上一级到项目根目录

DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'articles-db.json')
CURRENT_RUN_FILE = os.path.join(DATA_DIR, '.current-run')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')


def article_key(url, title=""):
    """生成文章唯一 key（URL 的 SHA-256 前 16 位，无 URL 则用标题 hash 加 t_ 前缀）"""
    if url:
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    if title:
        return 't_' + hashlib.sha256(title.encode('utf-8')).hexdigest()[:14]
    raise ValueError("article_key requires url or title")


def load_config():
    """读取 config.json（自动移除 # 注释行）"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = [line for line in content.split('\n') if not line.strip().startswith('#')]
    return json.loads('\n'.join(lines))


def _empty_db():
    """返回空的数据库结构"""
    return {
        "version": 1,
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {"totalArticles": 0, "totalPushed": 0},
        "articles": {}
    }


def load_db():
    """读取 articles-db.json，不存在则返回空数据库"""
    if not os.path.exists(DB_PATH):
        return _empty_db()
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return _empty_db()


def save_db(db):
    """原子写入 articles-db.json（先写临时文件再 rename，防损坏）"""
    db["lastUpdated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db["stats"]["totalArticles"] = len(db.get("articles", {}))
    db["stats"]["totalPushed"] = sum(
        1 for a in db.get("articles", {}).values() if a.get("status") == "pushed"
    )
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DB_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def get_run_dir(date_str=None):
    """获取当日运行目录路径（data/runs/YYYY-MM-DD/），自动创建"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    run_dir = os.path.join(DATA_DIR, 'runs', date_str)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_current_run(run_dir):
    """写入 .current-run 文件供后续脚本读取"""
    with open(CURRENT_RUN_FILE, 'w', encoding='utf-8') as f:
        f.write(run_dir)


def read_current_run():
    """读取 .current-run 文件，获取当前运行目录"""
    if not os.path.exists(CURRENT_RUN_FILE):
        return get_run_dir()
    with open(CURRENT_RUN_FILE, 'r', encoding='utf-8') as f:
        run_dir = f.read().strip()
    if not os.path.isdir(run_dir):
        return get_run_dir()
    return run_dir


def now_iso():
    """返回当前 UTC 时间 ISO 格式字符串"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
