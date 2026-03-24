#!/usr/bin/env python3
"""从配置文件抓取所有新闻源 — 支持 curl 和 browser 两种抓取模式"""

import json
import subprocess
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_config, get_run_dir, write_current_run, now_iso

# 模拟真实 Chrome 浏览器的请求头（2025 年版本）
CURL_HEADERS = [
    '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '-H', 'Accept-Language: pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    '-H', 'Accept-Encoding: gzip, deflate, br',
    '-H', 'Connection: keep-alive',
    '-H', 'Sec-Ch-Ua: "Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    '-H', 'Sec-Ch-Ua-Mobile: ?0',
    '-H', 'Sec-Ch-Ua-Platform: "Windows"',
    '-H', 'Sec-Fetch-Dest: document',
    '-H', 'Sec-Fetch-Mode: navigate',
    '-H', 'Sec-Fetch-Site: none',
    '-H', 'Sec-Fetch-User: ?1',
    '-H', 'Upgrade-Insecure-Requests: 1',
]


def fetch_via_curl(url, timeout=45):
    """用 curl 抓取，带真实浏览器请求头"""
    result = subprocess.run(
        ['curl', '-sL', '--max-time', str(timeout),
         '--compressed',          # 自动解压 gzip/br
         '--retry', '2',          # 失败重试 2 次
         '--retry-delay', '3',
         ] + CURL_HEADERS + [url],
        capture_output=True,
        text=True,
        timeout=timeout + 15
    )
    return result.stdout


def _ab_bin():
    """找到 agent-browser 可执行路径，返回命令列表"""
    import glob as _glob
    import shutil

    # 1. 本地 npx 缓存的原生二进制（最快）
    patterns = [
        os.path.expanduser('~/.npm/_npx/*/node_modules/agent-browser/bin/agent-browser-linux-x64'),
        os.path.expanduser('~/.npm/_npx/*/node_modules/agent-browser/bin/agent-browser-linux-arm64'),
    ]
    for pat in patterns:
        matches = _glob.glob(pat)
        if matches:
            return [matches[0]]

    # 2. 全局安装的 agent-browser（GitHub Actions: npm install -g）
    ab_path = shutil.which('agent-browser')
    if ab_path:
        return [ab_path]

    # 3. npx 启动（最慢但最通用）
    npx_path = shutil.which('npx')
    if npx_path:
        return [npx_path, 'agent-browser']

    return ['npx', 'agent-browser']


def fetch_via_browser(url, timeout=120):
    """用 agent-browser 抓取，绕过 Cloudflare 等反爬保护

    使用默认 session（共享 daemon），设置 60s 超时（默认 25s 太短）。
    """
    ab_cmd = _ab_bin()
    env = os.environ.copy()
    env['AGENT_BROWSER_DEFAULT_TIMEOUT'] = '60000'

    def run_ab(*args, input_text=None, t=75):
        return subprocess.run(
            ab_cmd + list(args),
            capture_output=True, text=True, timeout=t,
            env=env, input=input_text
        )

    try:
        # 打开页面
        r = run_ab('open', url)
        if r.returncode != 0:
            print(f"  ⚠️  browser open 失败: {r.stderr.strip()[:200]}")
            return ""

        # 等待动态内容渲染（Cloudflare challenge 需要 JS 执行时间）
        run_ab('wait', '5000', t=15)

        # 用 eval --stdin 获取 HTML（避免 shell 引号问题）
        r = run_ab('eval', '--stdin', input_text='document.documentElement.outerHTML')
        if r.returncode != 0:
            print(f"  ⚠️  browser eval 失败: {r.stderr.strip()[:200]}")
            return ""

        html = r.stdout.strip()
        # eval 返回 JS 字符串字面量，带引号需反转义
        if html.startswith('"') and html.endswith('"'):
            html = html[1:-1].replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

        return html

    except subprocess.TimeoutExpired:
        print(f"  ⚠️  browser 超时: {url}")
        return ""
    except Exception as e:
        print(f"  ⚠️  browser 抓取异常: {e}")
        return ""


def main():
    config = load_config()
    sources = config.get('sources', [])
    total_sources = len(sources)
    failed_sources = 0

    # 创建当日运行目录
    run_dir = get_run_dir()
    html_dir = os.path.join(run_dir, 'html')
    os.makedirs(html_dir, exist_ok=True)
    write_current_run(run_dir)

    print(f"📁 运行目录: {run_dir}")
    print(f"📊 新闻源数量: {total_sources}")

    raw_info = []

    for i, source in enumerate(sources, 1):
        name = source.get('name', '')
        url = source.get('url', '')
        lang = source.get('lang', '')
        category = source.get('category', '')
        fetch_mode = source.get('fetch_mode', 'curl')  # 默认 curl

        if not name or not url:
            print(f"⚠️  跳过无效源: {name}")
            continue

        mode_icon = "🌐" if fetch_mode == "browser" else "📡"
        print(f"{mode_icon} [{i}/{total_sources}] {name} [{fetch_mode}]")

        try:
            if fetch_mode == "browser":
                html = fetch_via_browser(url)
            else:
                html = fetch_via_curl(url)

            if not html or len(html) < 500:
                print(f"  ⚠️  抓取失败或内容过少: {name} ({len(html) if html else 0} 字节)")
                failed_sources += 1
                continue

            # 检测是否仍被拦截
            blocked_signals = ['403 Forbidden', 'Just a moment', 'cf-browser-verification', 'Enable JavaScript']
            if any(s in html[:2000] for s in blocked_signals):
                print(f"  ⚠️  被拦截（反爬保护）: {name}")
                failed_sources += 1
                continue

            html_filename = f"{name.replace(' ', '_')}.html"
            html_file = os.path.join(html_dir, html_filename)
            with open(html_file, 'w', encoding='utf-8', errors='replace') as f:
                f.write(html)

            raw_info.append({
                "source": name,
                "url": url,
                "lang": lang,
                "category": category,
                "fetchedAt": now_iso(),
                "htmlFile": html_filename,
                "fetchMode": fetch_mode,
            })

            print(f"  ✅ 抓取成功: {name} ({len(html):,} 字节)")

        except subprocess.TimeoutExpired:
            print(f"  ⚠️  超时: {name}")
            failed_sources += 1
        except Exception as e:
            print(f"  ⚠️  抓取失败: {name} - {str(e)}")
            failed_sources += 1

    # 写入 raw-headlines.json
    output_file = os.path.join(run_dir, 'raw-headlines.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(raw_info, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 抓取完成！")
    print(f"📊 共 {total_sources} 个源，成功 {len(raw_info)} 个，失败 {failed_sources} 个")
    print(f"📁 HTML 保存在: {html_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
