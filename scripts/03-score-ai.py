#!/usr/bin/env python3
"""AI评分 — 多提供者注册表，按 config.json 优先级自动降级"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_config, load_db, save_db, read_current_run

SYSTEM_PROMPT = """你是安哥拉华人社区的资深新闻编辑。

你的读者是生活在安哥拉的华人（商人、工程师、中企员工及其家属）。
请根据他们的实际阅读习惯和关注点，对每条新闻标题的"华人关注度"打分（1-10分）。

读者最关心的话题（高分 8-10）：
- 中国与安哥拉双边关系、中企在安投资项目、华人安全事件
- 安哥拉签证、居留、劳工政策变化
- 汇率（宽扎/美元/人民币）、石油价格、进出口政策
- 洛比托走廊等大型基建项目

读者较关心的话题（中分 5-7）：
- 安哥拉宏观经济（GDP、通胀、财政预算）
- 非洲或葡语国家与中国的贸易往来
- 安哥拉总统/政府重大决策
- 当地治安形势、社会稳定

读者较少关心的话题（低分 1-4）：
- 安哥拉国内党派政治纷争
- 体育、娱乐、文化活动
- 与华人无关的地方社会新闻

输出要求：严格只返回 JSON 数组，不要任何其他文字。
格式：[{"id":"文章id","score":分数}, ...]"""


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def read_env_file():
    """读取项目根目录 .env 文件"""
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if not os.path.exists(env_file):
        return {}
    result = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                result[k.strip()] = v.strip().strip('"\'')
    return result


def get_key(env_var, env_file_cache):
    """先查 os.environ，再查 .env 文件"""
    return os.environ.get(env_var, env_file_cache.get(env_var, ''))


def extract_scores(raw):
    """从模型返回中提取评分，容忍 markdown 包裹和末尾截断"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split('\n')
        raw = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    start = raw.find('[')
    end = raw.rfind(']') + 1

    if start != -1 and end > 0:
        try:
            items = json.loads(raw[start:end])
            return {i["id"]: int(i["score"]) for i in items if "id" in i and "score" in i}
        except json.JSONDecodeError:
            pass

    # 截断恢复：逐个提取完整的 {"id":...,"score":...} 对象
    objects = re.findall(r'\{"id"\s*:\s*"([^"]+)"\s*,\s*"score"\s*:\s*(\d+)\}', raw)
    if objects:
        return {oid: int(sc) for oid, sc in objects}
    return {}


# ─────────────────────────────────────────────
# 提供者实现
# ─────────────────────────────────────────────

def score_via_openai_compat(provider, articles, api_key):
    """通用 OpenAI 兼容模式评分（自动分批，适配思维链模型）"""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("缺少 openai 库，请运行: pip3 install openai")

    client = OpenAI(api_key=api_key, base_url=provider["base_url"])
    model = provider["model"]
    batch_size = provider.get("batch_size", 100)  # 默认每批100条；思维链模型建议50

    all_scores = {}

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        articles_text = "\n".join(
            f'{{"id":"{a["_key"]}","title":"{a["title"].strip()[:200].replace(chr(34), chr(39))}"}}'
            for a in batch
        )
        user_msg = f"请对以下 {len(batch)} 条新闻标题按华人关注度打分：\n\n{articles_text}"

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=16384,
        )
        raw = resp.choices[0].message.content.strip()
        batch_scores = extract_scores(raw)
        all_scores.update(batch_scores)

    return all_scores


def score_via_anthropic(provider, articles, api_key):
    """Anthropic 原生库评分（支持 Claude Haiku/Sonnet）"""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("缺少 anthropic 库，请运行: pip3 install anthropic")

    base_url = provider.get("base_url", "")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**kwargs)
    model = provider["model"]

    articles_text = "\n".join(
        f'{{"id":"{a["_key"]}","title":"{a["title"].strip()[:200].replace(chr(34), chr(39))}"}}'
        for a in articles
    )
    user_msg = f"请对以下 {len(articles)} 条新闻标题按华人关注度打分：\n\n{articles_text}"

    resp = client.messages.create(
        model=model,
        max_tokens=16384,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    raw = resp.content[0].text.strip()
    return extract_scores(raw)


def score_via_keyword(articles, config):
    """关键词评分（无需 API，兜底用）"""
    kw_high = config.get('scoring', {}).get('keywords_high', [])
    kw_mid = config.get('scoring', {}).get('keywords_medium', [])
    kw_low = config.get('scoring', {}).get('keywords_low', [])
    result = {}
    for art in articles:
        t = art.get("title", "")
        s = 3
        if any(re.search(k, t, re.IGNORECASE) for k in kw_high):
            s += 4
        elif any(re.search(k, t, re.IGNORECASE) for k in kw_mid):
            s += 2
        if any(re.search(k, t, re.IGNORECASE) for k in kw_low):
            s -= 1
        result[art["_key"]] = max(1, min(10, s))
    return result


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def run_providers(providers_cfg, articles, config, env_cache):
    """按优先级尝试各提供者，成功即返回"""
    for provider in providers_cfg:
        if not provider.get("enabled", False):
            continue

        name = provider["name"]
        ptype = provider.get("type", "openai-compat")

        if ptype == "keyword":
            print(f"📐 使用关键词评分（{name}）...")
            scores = score_via_keyword(articles, config)
            print(f"   ✅ 完成，评分 {len(scores)} 条")
            return scores, name

        # OpenAI 兼容模式
        api_key_env = provider.get("api_key_env", "")
        api_key = get_key(api_key_env, env_cache)
        if not api_key:
            print(f"   ⏭️  [{name}] 未找到 {api_key_env}，跳过")
            continue

        print(f"🤖 使用 {name}（{provider.get('model', '')}）评分 {len(articles)} 条...")
        try:
            if ptype == "anthropic":
                scores = score_via_anthropic(provider, articles, api_key)
            else:
                scores = score_via_openai_compat(provider, articles, api_key)
            coverage = len(scores) / len(articles)
            print(f"   返回 {len(scores)}/{len(articles)} 条（覆盖率 {coverage:.0%}）")

            if coverage >= 0.8:
                print(f"   ✅ {name} 成功")
                return scores, name
            else:
                print(f"   ⚠️  覆盖率不足 80%，尝试下一个提供者")
        except Exception as e:
            print(f"   ❌ {name} 失败: {e}，尝试下一个提供者")

    # 所有提供者都失败，强制关键词兜底
    print("⚠️  所有 AI 提供者失败，强制使用关键词评分")
    scores = score_via_keyword(articles, config)
    return scores, "keyword-fallback"


def list_providers(providers_cfg, env_cache):
    """打印当前所有提供者状态"""
    print("📋 评分提供者列表（按优先级）：")
    for i, p in enumerate(providers_cfg, 1):
        name = p["name"]
        enabled = p.get("enabled", False)
        ptype = p.get("type", "openai-compat")
        note = p.get("note", "")

        if ptype == "keyword":
            status = "✅ 就绪（无需 API）"
        elif not enabled:
            status = "⏸️  已禁用"
        else:
            key_env = p.get("api_key_env", "")
            key = get_key(key_env, env_cache)
            src = "环境变量" if os.environ.get(key_env) else ".env 文件"
            status = f"✅ 就绪（{key_env} 已配置 via {src}）" if key else f"❌ 缺少 {key_env}"

        print(f"  {i}. [{name}] {status}")
        if note:
            print(f"       {note}")


def main():
    # 支持 --list 参数查看提供者状态
    if "--list" in sys.argv:
        config = load_config()
        env_cache = read_env_file()
        providers_cfg = config.get("scoring", {}).get("providers", [])
        list_providers(providers_cfg, env_cache)
        return 0

    config = load_config()
    env_cache = read_env_file()
    providers_cfg = config.get("scoring", {}).get("providers", [])

    if not providers_cfg:
        print("❌ config.json 中未配置 scoring.providers")
        return 1

    run_dir = read_current_run()
    delta_file = os.path.join(run_dir, "delta-new.json")
    if not os.path.exists(delta_file):
        print(f"❌ 找不到增量文件: {delta_file}")
        return 1

    with open(delta_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = [a for a in data.get("articles", []) if a.get("title") and a.get("_key")]
    print(f"📊 待评分文章: {len(articles)} 条")

    if not articles:
        print("ℹ️  没有文章需要评分")
        output = {"date": data.get("date", ""), "total_new": 0, "total_filtered": 0, "articles": []}
        with open(os.path.join(run_dir, "filtered-candidates.json"), 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return 0

    # 运行提供者
    all_scores, used_provider = run_providers(providers_cfg, articles, config, env_cache)

    # 对未覆盖的条目用关键词兜底
    missing = [a for a in articles if a["_key"] not in all_scores]
    if missing:
        print(f"🔧 {len(missing)} 条未评分，关键词补全...")
        fallback = score_via_keyword(missing, config)
        all_scores.update(fallback)

    # 筛选 & 排序
    MIN_SCORE = config.get("pipeline", {}).get("minScore", 5)
    scored_articles = []
    for art in articles:
        score = all_scores.get(art["_key"])
        if score is not None:
            art["score"] = score
            if score >= MIN_SCORE:
                scored_articles.append(art)
    scored_articles.sort(key=lambda x: x["score"], reverse=True)

    # 更新数据库
    db = load_db()
    for art in articles:
        key = art["_key"]
        score = all_scores.get(key)
        if key in db["articles"] and score is not None:
            db["articles"][key]["score"] = score
            db["articles"][key]["status"] = "scored"
    save_db(db)

    # 保存结果
    today = data.get("date", "")
    output = {
        "date": today,
        "total_new": len(articles),
        "total_filtered": len(scored_articles),
        "scored_by": used_provider,
        "articles": scored_articles
    }
    output_file = os.path.join(run_dir, "filtered-candidates.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 在 data/ 根目录放一份最新副本
    import shutil
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    shutil.copy2(output_file, os.path.join(data_dir, "filtered-candidates.json"))

    print(f"\n✅ 评分完成（使用: {used_provider}）")
    print(f"📊 保留分数>={MIN_SCORE}: {len(scored_articles)}/{len(articles)} 条")
    print(f"📁 保存到: {output_file}")

    if scored_articles:
        print(f"\n📋 Top 10:")
        for i, art in enumerate(scored_articles[:10], 1):
            print(f"  {i}. [{art['score']}分] {art['title'][:70]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
