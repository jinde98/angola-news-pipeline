#!/usr/bin/env python3
import json
import time

# 读取过滤后的文章
with open('filtered_articles.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)

# 翻译映射（使用简单映射，实际可以用翻译API）
translations = {
    "Donald Trump pode adiar visita à China devido guerra no Médio Oriente": "唐纳德·特朗普因中东战争可能推迟访华",
    "Vice-presidente da Câmara de Comércio Angola-China…": "安哥拉-中国商会副主席……",
    "Chineses viram-se para os centros comerciais e concorrem entre si com...": "中国人转向购物中心，竞争激烈，投资超2500万美元...",
    "Dívida externa reduz 5% com mais de metade na mão da China…": "外债减少5%，超过一半由中国掌握……",
    "Banco da China aumenta capital social e deixa o russo VTB África…": "中国银行增加注册资本，俄罗斯VTB非洲被列入BNA黑名单……",
    "JLO prepara deslocação “desafiante” à China": "乔·洛伦索准备"挑战性"访问中国",
    "“A matriz [da relação com a China] deveria ser mudada do empréstimo…": "“与中国的[关系]矩阵应从贷款改为投资……",
    "Produtores chineses justificam importação com falta de mão-de-obra e matéria-prima": "中国生产商以缺乏劳动力和原材料为进口辩护",
    "China ceased to be Angola's largest creditor in 2025": "中国不再是最2025年最大的债权人",
    "Angolan govt reaffirms openness to foreign investment in oil sector": "安哥拉政府重申石油领域对外国投资开放",
    "Explosion hits deck of Sonangol oil tanker in Iraq": "伊拉克遇袭的Sonangol油轮爆炸",
    "Angola ganha com preço alto do petróleo, mas importações encarecem - Consultora": "安哥拉因高油价获益但进口成本上升 - 咨询公司",
    "Indústria transformadora impulsiona crescimento da economia não petrolífera, diz ministro": "转型工业推动非石油经济增长，部长称",
    "AGT – Estratégia de aumento da receita fiscal com preços de softwares certificados que promovem exclusão": "AGT - 通过推广具有排除性的认证软件提高税收收入策略"
}

# 生成Telegram消息
message = "📰 2026-03-16 安哥拉新闻精选\n\n"

for i, article in enumerate(articles, 1):
    title = article['title']
    source = article['source']

    # 尝试翻译
    if title in translations:
        chinese_title = translations[title]
    else:
        # 简单翻译（保留原标题）
        chinese_title = title

    # 生成消息行
    message += f"{i}【{source}】⭐{article['score']} {chinese_title}\n{article['url']}\n\n"

message += "---"

print(message)

# 保存到文件
with open('telegram_message.txt', 'w', encoding='utf-8') as f:
    f.write(message)
