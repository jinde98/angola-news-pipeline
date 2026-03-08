#!/usr/bin/env python3
"""从抓取的HTML中提取新闻标题、链接，与数据库对比输出增量"""

import re
import os
import sys
import json
import datetime
from html import unescape
from urllib.parse import urljoin
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_config, load_db, save_db, read_current_run, article_key, now_iso


def build_base_urls(config):
    """从 config.json 动态构建 BASE_URLS 映射（source name -> url）"""
    base_urls = {}
    for src in config.get('sources', []):
        key = src['name'].replace(' ', '_')
        base_urls[key] = src['url']
    return base_urls


def clean_text(text):
    """清理文本"""
    if not text:
        return ""
    text = unescape(text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text[:500]


def is_valid_url(url):
    """检查URL是否有效"""
    if not url or len(url) < 5:
        return False

    skip_patterns = [
        r'\.js$', r'wp-includes', r'wp-content/plugins', r'wp-content/themes',
        r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$', r'\.css$',
        r'wp-emoji', r'javascript:', r'mailto:',
    ]
    for pattern in skip_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False

    skip_paths = [
        r'/wp-admin/', r'/xmlrpc\.php', r'/wp-login\.php', r'robots\.txt',
        r'/category/', r'/tag/', r'/author/', r'/page/',
        r'category/', r'tag/', r'author/',
    ]
    for path in skip_paths:
        if path in url:
            return False

    if len(url) < 20:
        return False

    return True


def extract_articles(html, base_url, site_name):
    """从HTML中提取文章标题、链接"""
    seen_titles = OrderedDict()
    seen_urls = set()

    # 方法1: h2/h3 标签中的 a 链接
    pattern1 = r'<h[23][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h[23]>'
    for match in re.finditer(pattern1, html, re.DOTALL | re.IGNORECASE):
        url, title = match.group(1), clean_text(match.group(2))
        url = url.strip()
        title = title.strip()
        if is_valid_url(url):
            url = urljoin(base_url, url)
            if url not in seen_urls and title and len(title) > 5:
                seen_urls.add(url)
                seen_titles[title] = {"title": title, "url": url, "source": site_name}
            elif title in seen_titles:
                existing_url = seen_titles[title].get('url', '')
                if len(url) > len(existing_url):
                    seen_titles[title]["url"] = url
                    seen_urls.discard(existing_url)
                    seen_urls.add(url)

    # 方法2: article 标签
    pattern2 = r'<article[^>]*>.*?</article>'
    for article_match in re.finditer(pattern2, html, re.DOTALL | re.IGNORECASE):
        article_html = article_match.group(0)
        pattern2_h = r'<h[23][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h[23]>'
        for match in re.finditer(pattern2_h, article_html, re.DOTALL | re.IGNORECASE):
            url, title = match.group(1), clean_text(match.group(2))
            url = url.strip()
            title = title.strip()
            if is_valid_url(url):
                url = urljoin(base_url, url)
                if url in seen_urls:
                    continue
                if title and len(title) > 5:
                    seen_urls.add(url)
                    seen_titles[title] = {"title": title, "url": url, "source": site_name}

    # 方法3: class 包含 title/headline/entry 的 h2/h3
    pattern3 = r'<h[23][^>]*class=["\'][^"\']*(?:title|headline|entry)[^"\']*["\'][^>]*>(.*?)</h[23]>'
    for match in re.finditer(pattern3, html, re.DOTALL | re.IGNORECASE):
        title = clean_text(match.group(1))
        if title and len(title) > 5 and title not in seen_titles:
            seen_titles[title] = {"title": title, "url": "", "source": site_name}

    # 方法4: a 标签直接提取
    pattern4 = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    for match in re.finditer(pattern4, html, re.DOTALL | re.IGNORECASE):
        url, link_text = match.group(1), match.group(2)
        url = url.strip()
        link_text = clean_text(link_text)
        if is_valid_url(url):
            url = urljoin(base_url, url)
            if link_text and len(link_text) > 5:
                if url not in seen_urls and link_text not in seen_titles:
                    seen_urls.add(url)
                    seen_titles[link_text] = {"title": link_text, "url": url, "source": site_name}
                elif link_text in seen_titles:
                    existing_url = seen_titles[link_text].get('url', '')
                    if len(url) > len(existing_url):
                        seen_titles[link_text]["url"] = url
                        seen_urls.discard(existing_url)
                        seen_urls.add(url)

    # 方法5: 常见容器
    pattern5 = (r'<(div|article)[^>]*class=["\'][^"\']*?'
                r'(?:elementor-post|post|entry|article-item|card|item)[^"\']*["\'][^>]*>.*?'
                r'<h[23][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>(?:\s*</h[23])?')
    for match in re.finditer(pattern5, html, re.DOTALL | re.IGNORECASE):
        url, title = match.group(2), match.group(1)
        url = url.strip()
        title = clean_text(title)
        if is_valid_url(url):
            url = urljoin(base_url, url)
            if url not in seen_urls and title and len(title) > 5:
                seen_urls.add(url)
                seen_titles[title] = {"title": title, "url": url, "source": site_name}

    return list(seen_titles.values())


def main():
    run_dir = read_current_run()
    html_dir = os.path.join(run_dir, 'html')

    if not os.path.isdir(html_dir):
        print(f"❌ HTML 目录不存在: {html_dir}")
        return 1

    config = load_config()
    base_urls = build_base_urls(config)

    html_files = [f for f in sorted(os.listdir(html_dir)) if f.endswith('.html')]

    if not html_files:
        print("❌ 没有找到HTML文件")
        return 1

    all_articles = []

    for filename in html_files:
        site_key = filename.replace('.html', '')
        site_name = site_key.replace('_', ' ')

        if site_key not in base_urls:
            print(f"⚠️  未找到URL映射: {site_key}")
            continue

        base_url = base_urls[site_key]

        filepath = os.path.join(html_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception as e:
            print(f"❌ 读取文件失败 {filename}: {e}")
            continue

        if len(html) < 100:
            print(f"⚠️  HTML文件太小: {filename} ({len(html)} 字节)")
            continue

        articles = extract_articles(html, base_url, site_name)
        for art in articles:
            art["source"] = site_name
            all_articles.append(art)

        print(f"✅ {site_name}: {len(articles)} 篇")

    # 保存全量提取结果（调试用）
    today = os.path.basename(run_dir)
    extracted_output = {
        "date": today,
        "total": len(all_articles),
        "articles": all_articles
    }
    extracted_file = os.path.join(run_dir, "extracted-headlines.json")
    with open(extracted_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_output, f, ensure_ascii=False, indent=2)

    # 与数据库对比，计算增量
    db = load_db()
    timestamp = now_iso()
    new_articles = []
    updated_count = 0

    for art in all_articles:
        url = art.get('url', '')
        title = art.get('title', '')
        source = art.get('source', '')

        try:
            key = article_key(url, title)
        except ValueError:
            continue

        if key in db["articles"]:
            # 旧文章：只更新 lastSeen
            db["articles"][key]["lastSeen"] = timestamp
            updated_count += 1
        else:
            # 新文章：写入 DB 并加入增量列表
            db["articles"][key] = {
                "url": url,
                "title": title,
                "source": source,
                "firstSeen": timestamp,
                "lastSeen": timestamp,
                "status": "new",
                "runDate": today,
            }
            art["_key"] = key
            new_articles.append(art)

    save_db(db)

    # 保存增量文件
    delta_output = {
        "date": today,
        "total_extracted": len(all_articles),
        "total_new": len(new_articles),
        "total_existing": updated_count,
        "articles": new_articles
    }
    delta_file = os.path.join(run_dir, "delta-new.json")
    with open(delta_file, 'w', encoding='utf-8') as f:
        json.dump(delta_output, f, ensure_ascii=False, indent=2)

    # 在 data/ 根目录放一份最新副本，方便外部工具读取
    import shutil
    data_dir = os.path.dirname(run_dir.rstrip('/').rsplit('/runs', 1)[0] + '/x')  # → data/
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    shutil.copy2(extracted_file, os.path.join(data_dir, "extracted-headlines.json"))
    shutil.copy2(delta_file, os.path.join(data_dir, "delta-new.json"))

    print(f"\n✅ 提取完成")
    print(f"📊 全量提取: {len(all_articles)} 篇")
    print(f"📊 新文章: {len(new_articles)} 篇")
    print(f"📊 已存在（更新 lastSeen）: {updated_count} 篇")
    print(f"📁 全量: {extracted_file}")
    print(f"📁 增量: {delta_file}")

    source_counts = {}
    for art in new_articles:
        source = art.get("source", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    if source_counts:
        print(f"\n📊 新文章按源统计:")
        for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"  - {source}: {count} 条")

    return 0


if __name__ == "__main__":
    sys.exit(main())
