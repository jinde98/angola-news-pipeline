#!/usr/bin/env python3
"""
安哥拉新闻推送脚本
- URL去重
- 评分系统
- 翻译成中文
- 推送到Telegram
"""

import json
import requests
from datetime import datetime, timedelta
from datetime import timezone
from typing import List, Dict
from urllib.parse import urlparse

# 配置
TELEGRAM_TOKEN = "7285060575:AAEvQbltIqRAh5-kPbx9G3HlY_fYpDXc1q8"
TELEGRAM_CHAT_ID = "6295625531"

# 评分权重
SCORING = {
    "china_related": 10,      # 直接涉及中国/华人/中资企业
    "business": 7,            # 经济贸易/汇率/石油/进出口
    "political": 6,           # 重大政治事件
    "social": 5,              # 社会/安全/卫生事件
}

def load_sent_history():
    """加载已发送的URL历史"""
    try:
        with open("data/sent-history.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def load_articles():
    """加载新文章"""
    with open("data/runs/2026-03-11/extracted-headlines.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["articles"]

def is_over_2_days(article_date_str: str) -> bool:
    """检查文章是否超过2天"""
    try:
        # ANGOP 格式: 2026-03-11 13:27:00
        # 其他格式类似
        pub_date = datetime.strptime(article_date_str.split(" ")[0], "%Y-%m-%d")
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        return pub_date < cutoff
    except:
        return False

def score_article(title: str, url: str) -> int:
    """评分系统"""
    title_lower = title.lower()

    # 8-10分：涉及中国/华人/中资企业
    china_keywords = [
        "china", "chinesa", "chineses", "chinese", "macau",
        "retorno", "viagem", "china", "chuina"
    ]
    if any(kw in title_lower for kw in china_keywords):
        return SCORING["china_related"]

    # 6-7分：经济贸易/汇率/石油/进出口
    business_keywords = [
        "economia", "exportacao", "importacao", "comercio",
        "petroleo", "petróleo", "angop", "sonangol", "bna", "banco",
        "moneda", "moeda", "kwanza", "dolar", "dólar", "divisa",
        "investimento", "investimento", "fundo", "privatizacao",
        "fiscal", "fisco", "faturacao", "fatura", "factura",
        "electronic", "imposto", "taxa", "tarifa"
    ]
    if any(kw in title_lower for kw in business_keywords):
        return SCORING["business"]

    # 5分：重大政治/社会/安全事件
    if any(kw in title_lower for kw in ["governo", "presidente", "ministerio",
                                         "seguranca", "crime", "policia", "colera",
                                         "saude", "saúde", "acidente", "doença"]):
        return SCORING["social"]

    return 0

def translate_to_chinese(text: str) -> str:
    """翻译成中文（使用免费API）"""
    try:
        # 使用 MyMemory API（免费，无需注册）
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair=en|zh"
        response = requests.get(url, timeout=10)
        result = response.json()

        if result.get("responseStatus") == 200:
            return result["responseData"]["translatedText"]
        return text  # 翻译失败返回原标题
    except Exception as e:
        print(f"翻译失败: {e}")
        return text

def push_to_telegram(articles: List[Dict], date_str: str):
    """推送新闻到Telegram"""
    if not articles:
        print("没有新闻需要推送")
        return

    # 构建消息
    message = f"📰 {date_str} 安哥拉新闻精选\n\n"

    for i, article in enumerate(articles, 1):
        score = article["score"]
        source = article["source"]

        # 评分星级
        stars = "⭐" * (score // 3)

        # 中文标题
        chinese_title = translate_to_chinese(article["title"])
        if not chinese_title:
            chinese_title = "[翻译失败] " + article["title"]

        message += f"{i}.【{source}】{stars} {chinese_title}\n{article['url']}\n\n"

    # 发送消息
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"  # 使用HTML模式（支持换行）
    }

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print(f"✅ 成功推送 {len(articles)} 条新闻")
            return True
        else:
            print(f"❌ Telegram API错误: {result}")
            return False
    else:
        print(f"❌ HTTP错误: {response.status_code}")
        print(response.text)
        return False

def main():
    # 1. 加载数据
    sent_history = load_sent_history()
    articles = load_articles()
    print(f"📄 总文章数: {len(articles)}")
    print(f"📋 已发送历史: {len(sent_history)} 条")

    # 2. 过滤重复和旧文章
    filtered = []
    seen_urls = set(sent_history)

    for article in articles:
        url = article["url"]

        # 跳过已发送的文章
        if url in seen_urls:
            print(f"⏭️ 跳过已发送: {article['source']} - {article['title'][:50]}...")
            continue

        # 跳过超过2天的文章
        if article.get("published"):
            if is_over_2_days(article["published"]):
                print(f"⏭️ 跳过旧文章: {article['source']} - {article['title'][:50]}...")
                continue

        # 评分
        score = score_article(article["title"], url)

        if score >= 5:
            article["score"] = score
            filtered.append(article)
            seen_urls.add(url)  # 添加到已发送列表
            print(f"✅ 保留 [{score}] {article['source']}: {article['title'][:60]}...")

    print(f"\n🎯 过滤后: {len(filtered)} 条（目标最多15条）")

    # 3. 按评分排序，只保留15条最高评分
    final_articles = sorted(filtered, key=lambda x: x["score"], reverse=True)[:15]

    # 4. 推送到Telegram
    date_str = datetime.now().strftime("%Y-%m-%d")
    success = push_to_telegram(final_articles, date_str)

    # 5. 更新已发送历史
    if success:
        # 读取当前历史
        with open("data/sent-history.json", "r", encoding="utf-8") as f:
            history = set(json.load(f))

        # 添加新URL（只添加本次推送的15条）
        for article in final_articles:
            history.add(article["url"])

        # 保存
        with open("data/sent-history.json", "w", encoding="utf-8") as f:
            json.dump(list(history), f, ensure_ascii=False, indent=2)

        print(f"💾 已更新 sent-history.json ({len(history)} 条)")
    else:
        print("❌ 推送失败，不更新历史记录")

if __name__ == "__main__":
    main()
