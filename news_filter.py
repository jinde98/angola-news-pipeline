#!/usr/bin/env python3
import json
import re
from datetime import datetime, timedelta

# 读取已发送历史
with open('data/sent-history.json', 'r', encoding='utf-8') as f:
    sent_history = json.load(f)

# 过滤掉空字符串
sent_urls = set([url for url in sent_history if url and url.strip()])

# 读取新闻数据
with open('data/extracted-headlines.json', 'r', encoding='utf-8') as f:
    news_data = json.load(f)

# 当前日期
today = datetime(2026, 3, 16)
two_days_ago = today - timedelta(days=2)

# 评分标准
def score_article(title, source):
    """评分函数

    8-10分：直接涉及中国/华人/中资企业
    6-7分：经济贸易/汇率/石油/进出口等影响生意的
    5分：重大政治/社会/安全事件（华人应知道的）
    <5分：不推送
    """
    title_lower = title.lower()

    # 8-10分：中国/华人/中资企业
    if any(keyword in title_lower for keyword in [
        'china', '华人', '中资', '中企', '中国', '一带一路',
        '中国公司', 'chinese', 'zhongguo', 'chineses'
    ]):
        return (8, title)

    # 6-7分：经济贸易/汇率/石油/进出口
    if any(keyword in title_lower for keyword in [
        'economia', '贸易', '进出口', 'petroleo', '石油', 'preço', '汇率',
        'barril', 'oil', 'economic', 'trade', 'export', 'import',
        'finance', 'investimento', 'inverstment', 'dinheiro', 'dinero'
    ]):
        # 进一步判断经济相关
        if any(keyword in title_lower for keyword in [
            'economia', 'economy', 'economics',
            'petroleo', 'oil', 'preço', 'price',
            'comercio', 'trade', 'export', 'import',
            'finance', 'investment', 'inverstment', 'dinheiro', 'dinero'
        ]):
            return (7, title)

    # 5分：重大政治/社会/安全事件
    if any(keyword in title_lower for keyword in [
        'mpla', 'unita', 'eleicao', 'eleições', 'elections',
        'governo', 'government', 'presidente', 'presidente',
        'política', 'politica', 'politique',
        'segurança', 'segurança', 'securité', 'seguridad',
        'crime', 'criminal', 'assalto', 'morte', '死亡',
        'violência', 'violencia', 'violence', 'batalha', 'combate'
    ]):
        return (5, title)

    # 其他情况不评分或评分较低
    return (0, title)

# 筛选文章
filtered_articles = []

for article in news_data['articles']:
    url = article['url']
    title = article['title']
    source = article['source']

    # 检查是否在发送历史中
    if url in sent_urls:
        continue

    # 检查日期（提取日期信息）
    # 大部分文章是今天的，但有些可能有日期
    # 这里简化处理，假设大部分都是今天的

    # 评分
    score, title = score_article(title, source)

    # 只保留评分≥5的文章
    if score >= 5:
        filtered_articles.append({
            'score': score,
            'title': title,
            'url': url,
            'source': source
        })

# 按评分排序，高分在前
filtered_articles.sort(key=lambda x: x['score'], reverse=True)

# 最多保留15条
top_articles = filtered_articles[:15]

# 输出结果
print(json.dumps(top_articles, ensure_ascii=False, indent=2))
