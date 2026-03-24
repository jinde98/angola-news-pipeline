#!/usr/bin/env python3
"""
生成新闻评分报告（不推送）
"""

import json
from datetime import datetime, timedelta
from datetime import timezone

# 评分权重
SCORING = {
    "china_related": 10,
    "business": 7,
    "political": 6,
    "social": 5,
}

def load_articles():
    """加载新文章"""
    with open("data/runs/2026-03-11/extracted-headlines.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["articles"]

def score_article(title: str, url: str) -> int:
    """评分系统"""
    title_lower = title.lower()

    china_keywords = ["china", "chinesa", "chineses", "chinese", "macau"]
    if any(kw in title_lower for kw in china_keywords):
        return SCORING["china_related"]

    business_keywords = ["economia", "exportacao", "importacao", "comercio",
                        "petroleo", "angop", "sonangol", "bna", "banco",
                        "moneda", "moeda", "kwanza", "dolar", "divisa",
                        "investimento", "privatizacao", "fiscal", "fisco",
                        "faturacao", "factura", "electronic", "imposto"]
    if any(kw in title_lower for kw in business_keywords):
        return SCORING["business"]

    if any(kw in title_lower for kw in ["governo", "presidente", "ministerio",
                                         "seguranca", "crime", "policia", "colera",
                                         "saude", "saúde", "acidente"]):
        return SCORING["social"]

    return 0

def main():
    articles = load_articles()
    print(f"📊 总文章数: {len(articles)}")

    # 评分所有文章
    scored = []
    for article in articles:
        score = score_article(article["title"], article["url"])
        if score >= 5:
            article["score"] = score
            scored.append(article)

    print(f"🎯 评分≥5分: {len(scored)} 条\n")

    # 按评分排序
    sorted_articles = sorted(scored, key=lambda x: x["score"], reverse=True)

    # 显示前20条
    print("=" * 80)
    print(f"📰 2026-03-11 安哥拉新闻评分报告（Top 20）")
    print("=" * 80)

    for i, article in enumerate(sorted_articles[:20], 1):
        score = article["score"]
        source = article["source"]
        title = article["title"][:70]
        url = article["url"]

        stars = "⭐" * (score // 3)
        print(f"\n{i}. [{score}分] {source}")
        print(f"   {stars} {title}")
        print(f"   {url}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
