#!/usr/bin/env python3
"""一次性迁移脚本 — 从旧数据文件构建初始 articles-db.json"""

import json
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(__file__))
from utils import article_key, save_db, _empty_db, DATA_DIR, now_iso


def main():
    db = _empty_db()
    imported = 0
    timestamp = now_iso()

    # 1. 从 sent-history.json 导入已推送的 URL
    sent_file = os.path.join(DATA_DIR, 'sent-history.json')
    if os.path.exists(sent_file):
        try:
            with open(sent_file, 'r', encoding='utf-8') as f:
                sent_urls = json.load(f)
            if isinstance(sent_urls, list):
                for url in sent_urls:
                    if not url:
                        continue
                    key = article_key(url)
                    if key not in db["articles"]:
                        db["articles"][key] = {
                            "url": url,
                            "title": "",
                            "source": "",
                            "firstSeen": timestamp,
                            "lastSeen": timestamp,
                            "status": "pushed",
                            "pushedAt": timestamp,
                        }
                        imported += 1
            print(f"✅ sent-history.json: 导入 {imported} 条已推送 URL")
            # 备份
            shutil.copy2(sent_file, sent_file + '.bak')
            print(f"   备份到: {sent_file}.bak")
        except Exception as e:
            print(f"⚠️  sent-history.json 导入失败: {e}")

    # 2. 从 extracted-headlines.json 补充标题和源信息
    extracted_file = os.path.join(DATA_DIR, 'extracted-headlines.json')
    enriched = 0
    new_from_extracted = 0
    if os.path.exists(extracted_file):
        try:
            with open(extracted_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            articles = data.get('articles', [])
            for art in articles:
                url = art.get('url', '')
                title = art.get('title', '')
                source = art.get('source', '')
                try:
                    key = article_key(url, title)
                except ValueError:
                    continue
                if key in db["articles"]:
                    # 补充已有记录的标题和源
                    if title and not db["articles"][key].get("title"):
                        db["articles"][key]["title"] = title
                        enriched += 1
                    if source and not db["articles"][key].get("source"):
                        db["articles"][key]["source"] = source
                else:
                    db["articles"][key] = {
                        "url": url,
                        "title": title,
                        "source": source,
                        "firstSeen": timestamp,
                        "lastSeen": timestamp,
                        "status": "new",
                    }
                    new_from_extracted += 1
            print(f"✅ extracted-headlines.json: 补充 {enriched} 条标题，新增 {new_from_extracted} 条")
        except Exception as e:
            print(f"⚠️  extracted-headlines.json 导入失败: {e}")

    # 3. 从 translated-headlines.json 补充翻译和评分
    translated_file = os.path.join(DATA_DIR, 'translated-headlines.json')
    translated_count = 0
    if os.path.exists(translated_file):
        try:
            with open(translated_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            articles = data.get('articles', [])
            for art in articles:
                url = art.get('url', '')
                title = art.get('title', '')
                title_cn = art.get('title_cn', '')
                score = art.get('score', 0)
                source = art.get('source', '')
                try:
                    key = article_key(url, title)
                except ValueError:
                    continue
                if key in db["articles"]:
                    if title_cn:
                        db["articles"][key]["title_cn"] = title_cn
                        translated_count += 1
                    if score:
                        db["articles"][key]["score"] = score
                    if title and not db["articles"][key].get("title"):
                        db["articles"][key]["title"] = title
                    if source and not db["articles"][key].get("source"):
                        db["articles"][key]["source"] = source
                else:
                    db["articles"][key] = {
                        "url": url,
                        "title": title,
                        "title_cn": title_cn,
                        "source": source,
                        "score": score,
                        "firstSeen": timestamp,
                        "lastSeen": timestamp,
                        "status": "translated" if title_cn else "scored",
                    }
                    translated_count += 1
            print(f"✅ translated-headlines.json: 补充 {translated_count} 条翻译")
        except Exception as e:
            print(f"⚠️  translated-headlines.json 导入失败: {e}")

    # 4. 从 filtered-candidates.json 补充评分
    filtered_file = os.path.join(DATA_DIR, 'filtered-candidates.json')
    scored_count = 0
    if os.path.exists(filtered_file):
        try:
            with open(filtered_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            articles = data.get('articles', [])
            for art in articles:
                url = art.get('url', '')
                title = art.get('title', '')
                score = art.get('score', 0)
                try:
                    key = article_key(url, title)
                except ValueError:
                    continue
                if key in db["articles"] and score:
                    if not db["articles"][key].get("score"):
                        db["articles"][key]["score"] = score
                        scored_count += 1
            print(f"✅ filtered-candidates.json: 补充 {scored_count} 条评分")
        except Exception as e:
            print(f"⚠️  filtered-candidates.json 导入失败: {e}")

    # 5. 移动 data/*.html 到 data/runs/legacy/html/
    html_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.html')]
    if html_files:
        legacy_html_dir = os.path.join(DATA_DIR, 'runs', 'legacy', 'html')
        os.makedirs(legacy_html_dir, exist_ok=True)
        moved = 0
        for f in html_files:
            src = os.path.join(DATA_DIR, f)
            dst = os.path.join(legacy_html_dir, f)
            shutil.move(src, dst)
            moved += 1
        print(f"✅ 移动 {moved} 个 HTML 文件到 {legacy_html_dir}")

    # 保存数据库
    save_db(db)

    total = len(db["articles"])
    pushed = sum(1 for a in db["articles"].values() if a.get("status") == "pushed")
    with_title = sum(1 for a in db["articles"].values() if a.get("title"))
    with_cn = sum(1 for a in db["articles"].values() if a.get("title_cn"))

    print(f"\n📊 数据库统计:")
    print(f"   总文章数: {total}")
    print(f"   已推送: {pushed}")
    print(f"   有标题: {with_title}")
    print(f"   有中文翻译: {with_cn}")
    print(f"\n✅ 迁移完成！数据库保存在: {os.path.join(DATA_DIR, 'articles-db.json')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
