#!/usr/bin/env python3
"""使用 uapis.cn API 翻译新闻 — 批量发送（@@分隔），失败自动逐条重试"""

import json
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_db, save_db, read_current_run

API_URL = "https://uapis.cn/api/v1/translate/text"
BATCH_SEP = " @@ "
BATCH_SIZE = 5  # 每批翻译条数（太多内容相似的标题会被API合并）


def translate_single(title, retries=3):
    """单条翻译，带重试退避（批量失败时的 fallback）"""
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, json={"ToLang": "zh-CHS", "Text": title}, timeout=20)
            if resp.status_code == 200:
                result = resp.json()
                translation = (result.get('translate') or '').strip()
                if translation and len(translation) > 2:
                    return translation[:100]
                return None
            elif resp.status_code in (429, 502, 522):
                time.sleep(3 * (attempt + 1))
                continue
            else:
                return None
        except requests.exceptions.Timeout:
            time.sleep(3 * (attempt + 1))
            continue
        except Exception:
            return None
    return None


def translate_batch_request(titles, retries=2):
    """批量翻译：用 @@ 分隔合并发送，返回翻译列表（与输入等长）"""
    text = BATCH_SEP.join(titles)
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, json={"ToLang": "zh-CHS", "Text": text}, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                translated = (result.get('translate') or '').strip()
                parts = [p.strip() for p in translated.split('@@')]
                if len(parts) == len(titles):
                    return parts
                # 数量不匹配，返回 None 触发逐条 fallback
                return None
            elif resp.status_code in (429, 502, 522):
                time.sleep(4 * (attempt + 1))
                continue
            else:
                return None
        except requests.exceptions.Timeout:
            time.sleep(4 * (attempt + 1))
            continue
        except Exception:
            return None
    return None


def translate_all(articles):
    """分批翻译全部文章"""
    if not articles:
        return articles

    total = len(articles)
    print(f"🚀 批量翻译 {total} 条新闻（每批 {BATCH_SIZE} 条，@@ 分隔）...")

    translated_count = 0
    failed_count = 0

    for start in range(0, total, BATCH_SIZE):
        batch = articles[start:start + BATCH_SIZE]
        titles = [art.get('title', '') for art in batch]

        # 先尝试批量翻译
        results = translate_batch_request(titles)

        if results:
            # 批量成功
            for art, trans in zip(batch, results):
                if trans and len(trans) > 2:
                    art['title_cn'] = trans[:100]
                    translated_count += 1
                else:
                    failed_count += 1
        else:
            # 批量失败，逐条重试
            print(f"  ⚠️  批量翻译失败，逐条重试...")
            for art in batch:
                title = art.get('title', '')
                if not title or len(title) < 5:
                    continue
                trans = translate_single(title)
                if trans:
                    art['title_cn'] = trans
                    translated_count += 1
                else:
                    failed_count += 1
                time.sleep(1)

        done = min(start + BATCH_SIZE, total)
        print(f"  ✅ 进度: {done}/{total}（成功 {translated_count}，失败 {failed_count}）")

        # 批次间隔 2 秒
        if done < total:
            time.sleep(2)

    print(f"\n✅ 翻译完成！成功 {translated_count}/{total} 条" +
          (f"，失败 {failed_count} 条" if failed_count else ""))
    return articles


def main():
    run_dir = read_current_run()

    filtered_file = os.path.join(run_dir, "filtered-candidates.json")
    if not os.path.exists(filtered_file):
        print(f"❌ 找不到筛选文件: {filtered_file}")
        return 1

    with open(filtered_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data.get("articles", [])
    print(f"📊 总共 {len(articles)} 条新闻待翻译")

    if not articles:
        print("ℹ️  没有文章需要翻译")
        data['articles'] = []
        output_file = os.path.join(run_dir, "translated-headlines.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return 0

    articles = translate_all(articles)

    # 更新数据库
    db = load_db()
    for art in articles:
        key = art.get('_key', '')
        title_cn = art.get('title_cn', '')
        if key and key in db["articles"] and title_cn:
            db["articles"][key]["title_cn"] = title_cn
            db["articles"][key]["status"] = "translated"
    save_db(db)

    # 保存翻译结果
    data['articles'] = articles
    output_file = os.path.join(run_dir, "translated-headlines.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # data/ 根目录最新副本
    import shutil
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    shutil.copy2(output_file, os.path.join(data_dir, "translated-headlines.json"))

    print(f"📁 保存到: {output_file}")

    for i, art in enumerate(articles[:5], 1):
        title_cn = art.get('title_cn', art.get('title', ''))[:50]
        title_en = art.get('title', '')[:50]
        source = art.get('source', '')
        score = art.get('score', 0)
        print(f"{i}. [{source}] 评分:{score}")
        print(f"   中文: {title_cn}")
        print(f"   原文: {title_en}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
