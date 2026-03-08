# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

安哥拉新闻流水线：每日从 18 个安哥拉新闻网站（葡语/英语）抓取新闻，AI 评分筛选华人关注内容，翻译成中文，通过 Telegram 推送。

## 运行命令

```bash
# 完整流水线（一键执行全部步骤）
bash RUN_ALL.sh

# 分步执行
python3 scripts/01-fetch-headlines.py       # 步骤1: 抓取 18 个新闻源（curl + browser）
python3 scripts/02-extract-final.py data/   # 步骤2: 正则提取标题+链接，DB 去重，输出增量
python3 scripts/03-score-ai.py data/        # 步骤3: AI 评分（Gemini 优先），保留≥5分
python3 scripts/06-translate-agent.py data/ # 步骤4: uapis.cn 翻译成中文
python3 scripts/07-push-cn.py               # 步骤5: 推送到 Telegram

# 工具命令
python3 scripts/03-score-ai.py --list       # 查看评分提供者状态
python3 scripts/99-cleanup.py               # 清理旧运行目录和过期记录
```

## 项目结构

```
angola-news-pipeline/
├── CLAUDE.md              # 项目文档
├── config.json            # 配置（新闻源 + AI 评分提供者）
├── .env                   # API 密钥（ZHIPU_API_KEY, GEMINI_API_KEY）
├── RUN_ALL.sh             # 一键运行入口
├── scripts/
│   ├── utils.py                # 共享工具（DB读写、路径、配置）
│   ├── 01-fetch-headlines.py   # 抓取（curl + agent-browser）
│   ├── 02-extract-final.py     # 提取 + DB 去重 → delta-new.json
│   ├── 03-score-ai.py          # 多提供者 AI 评分
│   ├── 06-translate-agent.py   # uapis.cn 翻译
│   ├── 07-push-cn.py           # Telegram 推送
│   ├── 99-cleanup.py           # 清理旧数据
│   └── migrate-to-db.py        # 一次性历史迁移
└── data/
    ├── articles-db.json         # 文章主数据库（持久化，去重核心）
    ├── sent-history.json        # 历史推送记录
    ├── runs/
    │   └── YYYY-MM-DD/          # 每日运行目录
    │       ├── html/            # 原始 HTML
    │       ├── delta-new.json   # 增量新文章
    │       ├── filtered-candidates.json  # 评分筛选结果
    │       └── translated-headlines.json # 翻译结果
    └── .current-run             # 当前运行目录指针
```

## 环境变量

存储在项目根目录 `.env` 文件中：

- `ZHIPU_API_KEY` — 智谱 AI 密钥（GLM-4.7-Flash 评分备选）
- `GEMINI_API_KEY` — Google Gemini 密钥（默认评分模型）
- Telegram 凭证在 `scripts/07-push-cn.py` 中（`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`）

## 流水线架构

```
抓取(curl/browser) → HTML → 正则提取标题 → DB去重(增量) → AI评分筛选 → 翻译 → Telegram推送
```

### 数据流

| 步骤 | 输入 | 输出 | 脚本 |
|------|------|------|------|
| 清理 | data/runs/*, articles-db.json | 删除过期 | 99-cleanup.py |
| 抓取 | config.json sources | runs/YYYY-MM-DD/html/*.html | 01-fetch-headlines.py |
| 提取 | html/*.html + articles-db.json | delta-new.json（增量） | 02-extract-final.py |
| 评分 | delta-new.json | filtered-candidates.json | 03-score-ai.py |
| 翻译 | filtered-candidates.json | translated-headlines.json | 06-translate-agent.py |
| 推送 | translated-headlines.json | Telegram 消息 + DB 更新 | 07-push-cn.py |

### 增量去重机制

- `data/articles-db.json` 存储所有文章的 SHA-256 URL 哈希（前 16 位）
- 提取阶段对比 DB，只输出全新文章到 `delta-new.json`
- 已存在的文章仅更新 `lastSeen` 时间戳
- 文章状态流转：`new` → `scored` → `translated` → `pushed`
- 超过 30 天的记录由 `99-cleanup.py` 清除

### AI 评分机制（03-score-ai.py）

多提供者注册表，按 `config.json` 中 `scoring.providers` 数组顺序自动降级：

1. **Gemini 2.5 Flash**（默认首选，免费额度大）
2. **GLM-4.7-Flash**（备选，免费思维链模型，每批 50 条）
3. **Claude Haiku**（Claude Code 环境自带 key）
4. **关键词评分**（最终兜底，无需 API）

覆盖率 ≥80% 即认为成功，否则自动尝试下一个提供者。支持分批处理（`batch_size` 配置）。

评分提示词基于安哥拉华人实际阅读习惯：中企投资、签证政策、汇率石油等得高分（8-10），宏观经济得中分（5-7），党派纷争体育娱乐得低分（1-4）。

### 抓取模式

- **curl**（默认）：带 Chrome UA 和请求头，适用大多数网站
- **browser**（agent-browser）：用于 Cloudflare/JS 渲染网站，config.json 中设 `"fetch_mode": "browser"`
- 当前使用 browser 模式的源：Reporter Angola、Jornal de Angola

## 关键设计决策

- **HTML 解析用正则而非 BeautifulSoup**：5 种模式逐层匹配，适配不同网站结构
- **config.json 支持注释**：脚本自动移除 `#` 开头的行再解析 JSON
- **原子写入 DB**：tempfile + os.replace() 防止写入中断损坏
- **每日隔离运行目录**：`data/runs/YYYY-MM-DD/`，互不干扰
- **所有路径使用绝对路径**：基础目录硬编码为 `/home/jd/.openclaw/workspace/angola-news-pipeline`
- **增量为 0 提前退出**：RUN_ALL.sh 在无新文章或筛选为 0 时自动停止，节省 API 调用

## 添加新的评分 API 提供者

在 `config.json` 的 `scoring.providers` 数组中添加：

```json
{
  "name": "新提供者名",
  "enabled": true,
  "type": "openai-compat",
  "base_url": "https://api.example.com/v1/",
  "model": "model-name",
  "api_key_env": "YOUR_API_KEY",
  "batch_size": 100,
  "note": "说明"
}
```

支持的 type：`openai-compat`（OpenAI 兼容接口）、`anthropic`（Anthropic 原生接口）、`keyword`（关键词兜底）。
