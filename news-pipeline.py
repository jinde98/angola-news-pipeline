#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安哥拉新闻推送脚本
"""
import json
import re
from datetime import datetime, timedelta

# 评分标准
SCORE_CHINA = 10  # 直接涉及中国/华人/中资企业
SCORE_ECONOMY = 7  # 经济贸易/汇率/石油/进出口等影响生意
SCORE_MAJOR = 5    # 重大政治/社会/安全事件（华人应知道的）
SCORE_NORMAL = 3   # 其他常规新闻

def get_score(title):
    """根据标题评分"""
    title_lower = title.lower()

    # 10分：涉及中国/华人/中资企业
    if any(keyword in title_lower for keyword in ['china', 'chinesa', 'chineses', 'chinese',
                                                   'chinese company', 'china company',
                                                   'hong kong', 'macau', 'dao shui',
                                                   'acrrep', 'pan china',
                                                   'refinaria de luanda', 'refinery',
                                                   'telecom', 'mpla']):
        return SCORE_CHINA

    # 7分：经济贸易/汇率/石油/进出口等影响生意
    if any(keyword in title_lower for keyword in [
        'angola', 'angolano', 'angola economico',
        'banco nacional', 'bna', 'banco central',
        'sonangol', 'petroleo', 'oleo',
        'exportacao', 'importacao', 'comercio',
        'petroleo', 'dolar', 'kwanza', 'kz',
        'investimento', 'privatizacao', 'fiscal',
        'concessao', 'bloco', 'campo',
        'economia', 'economica', 'economico',
        'imposto', 'taxa', 'tarifa',
        'emprego', 'desemprego', 'trabalho',
        'investidor', 'inversor',
        'jugadores', 'pedras', 'sodiam',
        'refinaria', 'kilamba', 'fusao',
        'fundo', 'pensao', 'pension',
        'accao', 'accao social',
        'gafi', 'lista cinzenta',
        'facturacao', 'electronica', 'nfif',
        'municipio', 'prefeitura',
        'sobre comercio',
        'exportacoes',
        'da ong china'
    ]):
        return SCORE_ECONOMY

    # 5分：重大政治/社会/安全事件（华人应知道）
    if any(keyword in title_lower for keyword in [
        'presidente', 'joao lourenco',
        'papa', 'leao xiv',
        'policia', 'pn', 'policial',
        'prisao', 'prision', 'pena',
        'violacao', 'rape', 'crimes',
        'assalto', 'roubo', 'ladrão',
        'colera', 'doenca', 'saude',
        'inundacao', 'chuva',
        'protesto', 'tumulto',
        'funeral', 'funerario',
        'conflito', 'guerra',
        'canoa', 'navio',
        'chinesa', 'cidada',
        'reuniao', 'conferencia',
        'palestra', 'discurso',
        'missao', 'enviado',
        'atentado', 'ataque',
        'seguranca',
        'crime', 'criminoso',
        'shooting', 'tiroteio',
        'trabalhador', 'trabalho',
        'acidente', 'acidente mototaxi',
        'falecimento', 'falecido',
        'morte', 'mortos',
        'homicidio', 'assassinato',
        'procurador', 'pgr',
        'interpol', 'extradicao',
        'limpeza', 'limpar',
        'atraco', 'assalto',
        'ataques', 'ataque'
    ]):
        return SCORE_MAJOR

    return SCORE_NORMAL

def translate_to_chinese(title):
    """简单的标题翻译（中文）"""
    # 这里使用一个简单的规则引擎进行翻译
    # 实际应该调用翻译API，但为了简化，我们使用映射

    translations = {
        # 通用模式
        "national": "全国",
        "politics": "政治",
        "economy": "经济",
        "society": "社会",
        "education": "教育",
        "health": "健康",
        "security": "安全",
        "transport": "交通",
        "tourism": "旅游",
        "agriculture": "农业",
        "industry": "工业",
        "energy": "能源",
        "finance": "金融",
        "work": "工作",
        "news": "新闻",
        "latest": "最新",
        "most viewed": "最受欢迎",
        "top news": "头条新闻",
        "institutions": "机构",
        "revista": "杂志",
        "press release": "新闻稿",
        "report": "报告",
        "analysis": "分析",
        "interview": "采访",
        "commentary": "评论",
        "opinion": "观点",
        "special": "特写",
        "series": "系列",

        # 新闻实体
        "president": "总统",
        "joao lourenco": "洛伦索总统",
        "pope": "教皇",
        "leao xiv": "利奥十四世",
        "policia": "警察",
        "sonangol": "国家石油公司",
        "bna": "国家银行",
        "bpc": "波亚斯储蓄银行",
        "acrep": "安哥拉华人企业商会",
        "pan china": "Pan China",
        "cimenfort": "Cimenfort",
        "diariodosnegocios": "商业日报",
        "jornaloguardiao": "卫士报",
        "angop": "安哥拉通讯社",
        "valor economico": "经济价值",
        "ecos do henda": "Henda杂讯",
        "na mira do crime": "犯罪前沿",
        "angola24horas": "安哥拉24小时",
        "opais": "国家报",
        "jornal de angola": "安哥拉日报",
        "club k": "K俱乐部",
        "correio kianda": "基兰达邮报",
        "novo jornal": "新报",
        "the guardian": "卫士报",
        "expansao": "扩张",
        "forbes africa": "福布斯非洲",
        "hold on angola": "Angola停不下来",
        "na mira do crime": "犯罪前沿",
        "negocios de angola": "安哥拉商业",
        "reporter angola": "安哥拉记者",
        "ver angola": "Ver Angola",
        "mundo": "世界",
        "chinês": "中文",
        "china": "中国",
        "chinesa": "中国",
        "chineses": "中国",
        "chinese": "中国",
        "hong kong": "香港",
        "macau": "澳门",
        "dao shui": "道瑞",
        "acrrep": "安哥拉华人企业商会",
        "pan china": "Pan China",
        "refinaria de luanda": "罗安达炼油厂",
        "refinery": "炼油厂",
        "telecom": "电信",
        "mpla": "安哥拉解放运动",
        "unita": "安哥拉团结与民族解放运动",
        "frente de libertacao de angola": "安哥拉解放阵线",
        "pdp-r": "安哥拉人民解放运动",
    }

    # 尝试模式匹配
    title_lower = title.lower()

    for english, chinese in translations.items():
        if english in title_lower:
            # 替换第一个出现
            title = re.sub(rf'\b{english}\b', chinese, title, count=1)

    # 如果标题仍然包含葡萄牙语关键字，尝试翻译
    title = re.sub(r'\b\b\d+\b', '', title)  # 移除数字

    return title

def filter_and_score_articles():
    """过滤和评分文章"""
    # 读取提取的文章
    with open('/home/jd/.openclaw/workspace/angola-news-pipeline/data/extracted-headlines.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 读取已发送的URL列表
    with open('/home/jd/.openclaw/workspace/angola-news-pipeline/data/sent-history.json', 'r', encoding='utf-8') as f:
        sent_urls = set(json.load(f))

    articles = []
    for article in data.get('articles', []):
        url = article['url']
        title = article['title']
        source = article['source']

        # 跳过分类页面和普通导航页面
        if url.endswith('/') or 'assuntos-relacionados' in url or 'vtab=' in url:
            continue

        # 跳过已发送的URL
        if url in sent_urls:
            continue

        # 评分
        score = get_score(title)

        # 只保留>=5分的文章
        if score >= 5:
            # 翻译标题
            translated_title = translate_to_chinese(title)

            articles.append({
                'title': title,
                'translated_title': translated_title,
                'url': url,
                'source': source,
                'score': score
            })

    # 按分数排序，分数高的在前
    articles.sort(key=lambda x: x['score'], reverse=True)

    # 最多保留15条
    articles = articles[:15]

    return articles

def format_message(articles):
    """格式化消息"""
    today = datetime.now().strftime('%Y-%m-%d')
    message = f'📰 {today} 安哥拉新闻精选\n\n'

    for i, article in enumerate(articles, 1):
        # 评分星数
        stars = '⭐' * article['score']
        message += f'{i}.' + f'【{article["source"]}】{stars} {article["translated_title"]}\n'
        message += f'   {article["url"]}\n\n'

    return message

def main():
    # 过滤和评分文章
    articles = filter_and_score_articles()

    if not articles:
        print('没有新文章需要推送')
        return

    # 格式化消息
    message = format_message(articles)

    # 打印预览
    print(f'找到 {len(articles)} 篇新文章需要推送：')
    for article in articles:
        print(f"  [{article['score']}] {article['title'][:50]}...")
    print()

    # 推送到 Telegram
    import subprocess
    result = subprocess.run([
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--target', '6295625531',
        '--message', message,
        '--silent'
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print('✅ 推送成功')

        # 读取已发送URL列表
        with open('/home/jd/.openclaw/workspace/angola-news-pipeline/data/sent-history.json', 'r', encoding='utf-8') as f:
            sent_urls = set(json.load(f))

        # 添加新的URL
        for article in articles:
            sent_urls.add(article['url'])

        # 写回文件
        with open('/home/jd/.openclaw/workspace/angola-news-pipeline/data/sent-history.json', 'w', encoding='utf-8') as f:
            json.dump(list(sent_urls), f, ensure_ascii=False, indent=2)

        print(f'✅ 已记录 {len(articles)} 篇文章到 sent-history.json')
    else:
        print(f'❌ 推送失败: {result.stderr}')
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
