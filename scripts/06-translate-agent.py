#!/usr/bin/env python3
"""翻译新闻标题 — 优先 AI 翻译（Gemini/GLM/Claude），失败回退 uapis.cn"""

import json
import os
import re
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_config, load_db, save_db, read_current_run

# ─────────────────────────────────────────────
# AI 翻译提示词
# ─────────────────────────────────────────────

TRANSLATE_PROMPT = """你是一位专业的新闻标题翻译专家，精通葡萄牙语、英语和中文。

请将以下新闻标题翻译成简体中文。要求：
- 翻译简洁准确，符合中文新闻标题习惯
- 人名保留原文（括号标注中文），地名使用通用中文译法
- 安哥拉常见译法：Luanda=罗安达，Kwanza=宽扎，Lobito=洛比托，Cabinda=卡宾达
- 每条翻译控制在50字以内

严格只返回 JSON 数组，格式：[{"id":"文章id","title_cn":"中文翻译"}, ...]"""


# ─────────────────────────────────────────────
# 工具函数（复用评分脚本的模式）
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


def get_key(env_var, env_cache):
    return os.environ.get(env_var, env_cache.get(env_var, ''))


def extract_translations(raw):
    """从 AI 返回中提取翻译结果，容忍 markdown 包裹和截断"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split('\n')
        raw = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    start = raw.find('[')
    end = raw.rfind(']') + 1

    if start != -1 and end > 0:
        try:
            items = json.loads(raw[start:end])
            return {i["id"]: i["title_cn"].strip() for i in items
                    if "id" in i and "title_cn" in i and i["title_cn"].strip()}
        except (json.JSONDecodeError, KeyError):
            pass

    # 截断恢复：逐个提取
    objects = re.findall(
        r'\{"id"\s*:\s*"([^"]+)"\s*,\s*"title_cn"\s*:\s*"([^"]+)"\}', raw
    )
    if objects:
        return {oid: cn.strip() for oid, cn in objects}
    return {}


# ─────────────────────────────────────────────
# AI 翻译提供者
# ─────────────────────────────────────────────

def translate_via_openai_compat(provider, articles, api_key):
    """OpenAI 兼容接口翻译（Gemini/GLM 等）"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=provider["base_url"])
    model = provider["model"]
    batch_size = provider.get("batch_size", 100)

    all_translations = {}

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        articles_text = "\n".join(
            f'{{"id":"{a["_key"]}","title":"{a["title"].strip()[:200].replace(chr(34), chr(39))}"}}'
            for a in batch
        )
        user_msg = f"请翻译以下 {len(batch)} 条新闻标题：\n\n{articles_text}"

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=16384,
        )
        raw = resp.choices[0].message.content.strip()
        batch_trans = extract_translations(raw)
        all_translations.update(batch_trans)

    return all_translations


def translate_via_anthropic(provider, articles, api_key):
    """Anthropic 原生接口翻译"""
    import anthropic

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
    user_msg = f"请翻译以下 {len(articles)} 条新闻标题：\n\n{articles_text}"

    resp = client.messages.create(
        model=model,
        max_tokens=16384,
        system=TRANSLATE_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    raw = resp.content[0].text.strip()
    return extract_translations(raw)


# ─────────────────────────────────────────────
# uapis.cn 翻译（兜底）
# ─────────────────────────────────────────────

UAPIS_URL = "https://uapis.cn/api/v1/translate/text"
UAPIS_BATCH_SEP = " @@ "
UAPIS_BATCH_SIZE = 5


def uapis_single(title, retries=3):
    """uapis.cn 单条翻译"""
    for attempt in range(retries):
        try:
            resp = requests.post(UAPIS_URL, json={"ToLang": "zh-CHS", "Text": title}, timeout=20)
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


def uapis_batch(titles, retries=2):
    """uapis.cn 批量翻译（@@ 分隔）"""
    text = UAPIS_BATCH_SEP.join(titles)
    for attempt in range(retries):
        try:
            resp = requests.post(UAPIS_URL, json={"ToLang": "zh-CHS", "Text": text}, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                translated = (result.get('translate') or '').strip()
                parts = [p.strip() for p in translated.split('@@')]
                if len(parts) == len(titles):
                    return parts
                return None
            elif resp.status_code in (429, 502, 522):
                time.sleep(4 * (attempt + 1))
                continue
            else:
                return None
        except Exception:
            return None
    return None


def translate_via_uapis(articles):
    """uapis.cn 翻译全部文章（批量 + 逐条兜底）"""
    results = {}
    total = len(articles)

    for start in range(0, total, UAPIS_BATCH_SIZE):
        batch = articles[start:start + UAPIS_BATCH_SIZE]
        titles = [art.get('title', '') for art in batch]

        batch_results = uapis_batch(titles)

        if batch_results:
            for art, trans in zip(batch, batch_results):
                if trans and len(trans) > 2:
                    results[art['_key']] = trans[:100]
        else:
            print(f"  ⚠️  uapis 批量失败，逐条重试...")
            for art in batch:
                title = art.get('title', '')
                if not title or len(title) < 5:
                    continue
                trans = uapis_single(title)
                if trans:
                    results[art['_key']] = trans[:100]
                time.sleep(1)

        if start + UAPIS_BATCH_SIZE < total:
            time.sleep(2)

    return results


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def run_translation(providers_cfg, articles, env_cache):
    """按优先级尝试 AI 翻译，全部失败则用 uapis.cn"""
    for provider in providers_cfg:
        if not provider.get("enabled", False):
            continue

        name = provider["name"]
        ptype = provider.get("type", "openai-compat")

        # 跳过关键词提供者（仅用于评分）
        if ptype == "keyword":
            continue

        api_key_env = provider.get("api_key_env", "")
        api_key = get_key(api_key_env, env_cache)
        if not api_key:
            print(f"  ⏭️  [{name}] 未找到 {api_key_env}，跳过")
            continue

        print(f"🤖 使用 {name}（{provider.get('model', '')}）翻译 {len(articles)} 条...")
        try:
            if ptype == "anthropic":
                translations = translate_via_anthropic(provider, articles, api_key)
            else:
                translations = translate_via_openai_compat(provider, articles, api_key)

            coverage = len(translations) / len(articles) if articles else 0
            print(f"   返回 {len(translations)}/{len(articles)} 条（覆盖率 {coverage:.0%}）")

            if coverage >= 0.8:
                print(f"   ✅ {name} 翻译成功")
                return translations, name
            else:
                print(f"   ⚠️  覆盖率不足 80%，尝试下一个提供者")
        except Exception as e:
            print(f"   ❌ {name} 翻译失败: {e}")

    # 所有 AI 提供者失败，回退 uapis.cn
    print("🔄 AI 翻译不可用，使用 uapis.cn 免费翻译...")
    translations = translate_via_uapis(articles)
    return translations, "uapis.cn"


def main():
    config = load_config()
    env_cache = read_env_file()
    providers_cfg = config.get("scoring", {}).get("providers", [])

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

    # 运行翻译
    translations, used_provider = run_translation(providers_cfg, articles, env_cache)

    # AI 未覆盖的条目用 uapis.cn 补全
    missing = [a for a in articles if a["_key"] not in translations]
    if missing:
        print(f"🔧 {len(missing)} 条未翻译，uapis.cn 补全...")
        fallback = translate_via_uapis(missing)
        translations.update(fallback)

    # 写入翻译结果
    translated_count = 0
    for art in articles:
        cn = translations.get(art.get('_key', ''), '')
        if cn:
            art['title_cn'] = cn[:100]
            translated_count += 1

    failed_count = len(articles) - translated_count
    print(f"\n✅ 翻译完成（使用: {used_provider}）！成功 {translated_count}/{len(articles)} 条" +
          (f"，失败 {failed_count} 条" if failed_count else ""))

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
