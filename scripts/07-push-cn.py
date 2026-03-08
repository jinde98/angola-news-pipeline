#!/usr/bin/env python3
"""推送安哥拉新闻到 Telegram（中文标题）— 更新数据库标记为 pushed"""

import json
import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_db, save_db, read_current_run, now_iso

# Telegram 凭证从环境变量读取
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '6479792576:AAFBSPDwTgPCuGYsog6JdfdXa1Vx-GbGlE4')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6295625531')

BATCH_SIZE = 15
MAX_MESSAGE_LENGTH = 3000


def build_message(articles, date_str):
    """构建单条Telegram消息"""
    msg = f"📰 {date_str} 安哥拉新闻精选\n\n"
    msg += f"📊 共 {len(articles)} 篇（分数>=4）\n\n"
    msg += "---\n"

    for i, article in enumerate(articles, 1):
        title_cn = article.get('title_cn', '')
        title_en = article.get('title', '')
        url = article.get('url', '')
        source = article.get('source', '')
        score = article.get('score', 0)

        title = title_cn if title_cn else title_en

        msg += f"{i}. 【{source}】{title}\n"
        msg += f"   📊 评分: {score}/10\n"
        if url:
            msg += f"   🔗 {url}\n"
        msg += "\n"

    return msg


def send_telegram_message(text):
    """发送 Telegram 消息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}

    try:
        resp = requests.post(url, json=payload, timeout=30)
        result = resp.json()
        if result.get('ok'):
            return result['result']['message_id']
        else:
            print(f"   ❌ 发送失败: {result.get('description')}")
            return None
    except Exception as e:
        print(f"   ❌ 发送异常: {e}")
        return None


def main():
    run_dir = read_current_run()

    # 读取翻译后的文件
    translated_file = os.path.join(run_dir, "translated-headlines.json")
    if not os.path.exists(translated_file):
        print(f"❌ 找不到翻译文件: {translated_file}")
        return 1

    with open(translated_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data.get("articles", [])
    print(f"📰 推送安哥拉新闻")
    print(f"📊 总共 {len(articles)} 条新闻")

    if not articles:
        print("ℹ️  没有文章需要推送")
        return 0

    # 筛选高分新闻
    high_score_articles = [art for art in articles if art.get('score', 0) >= 4]
    high_score_articles.sort(key=lambda x: x.get('score', 0), reverse=True)
    print(f"📊 筛选出 {len(high_score_articles)} 条高分新闻（分数>=4）")

    if not high_score_articles:
        print("ℹ️  没有高分文章需要推送")
        return 0

    news_date = data.get("date", datetime.now().strftime('%Y-%m-%d'))

    # 分段推送
    all_message_ids = []
    articles_per_message = min(BATCH_SIZE, len(high_score_articles))

    for batch_start in range(0, len(high_score_articles), articles_per_message):
        batch_end = min(batch_start + articles_per_message, len(high_score_articles))
        batch = high_score_articles[batch_start:batch_end]

        message = build_message(batch, news_date)
        batch_num = batch_start // articles_per_message + 1
        total_batches = (len(high_score_articles) - 1) // articles_per_message + 1

        print(f"🚀 推送第 {batch_num}/{total_batches} 批，{len(batch)} 条新闻...")

        msg_id = send_telegram_message(message)
        if msg_id:
            all_message_ids.append(msg_id)
            print(f"   ✅ 成功 (消息 ID: {msg_id}, 长度: {len(message)} 字符)")

    # 更新数据库标记为 pushed
    db = load_db()
    pushed_time = now_iso()
    pushed_count = 0

    for art in high_score_articles:
        key = art.get('_key', '')
        if key and key in db["articles"]:
            db["articles"][key]["status"] = "pushed"
            db["articles"][key]["pushedAt"] = pushed_time
            pushed_count += 1

    save_db(db)

    print(f"\n✅ 推送完成！")
    print(f"📊 推送 {len(all_message_ids)} 条消息，更新 {pushed_count} 条数据库记录")

    return 0


if __name__ == "__main__":
    sys.exit(main())
