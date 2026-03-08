# 安哥拉新闻流水线 (Angola News Pipeline)

每日从 18 个安哥拉新闻网站（葡语/英语）自动抓取新闻，通过 AI 评分筛选华人关注内容，翻译成中文，并推送到 Telegram。

## 功能特性

- 🌐 **多源爬取**: 从 18 个安哥拉新闻源抓取最新新闻
- 🤖 **AI 评分**: 多提供者支持（Gemini、GLM、Claude），自动降级
- 📝 **自动翻译**: 支持葡语/英语到中文翻译
- 📱 **Telegram 推送**: 自动推送高分新闻到 Telegram 频道
- 💾 **增量处理**: 智能去重，只处理新文章，避免重复推送
- 🔄 **自动化**: 支持定时运行（GitHub Actions）

## 项目结构

```
angola-news-pipeline/
├── CLAUDE.md                    # 项目开发文档
├── config.json                  # 新闻源配置 + AI 评分提供者
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖
├── RUN_ALL.sh                   # 一键运行脚本
├── scripts/
│   ├── 01-fetch-headlines.py    # 抓取阶段（curl + browser）
│   ├── 02-extract-final.py      # 提取 + 去重阶段
│   ├── 03-score-ai.py           # AI 评分阶段
│   ├── 06-translate-agent.py    # 翻译阶段
│   ├── 07-push-cn.py            # Telegram 推送阶段
│   ├── 99-cleanup.py            # 清理旧数据
│   ├── migrate-to-db.py         # 一次性历史迁移
│   └── utils.py                 # 共享工具函数
├── data/
│   ├── articles-db.json         # 文章数据库（去重核心）
│   ├── sent-history.json        # 推送历史
│   └── runs/                    # 每日运行目录（按日期分隔）
└── templates/                   # HTML 解析模板
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/angola-news-pipeline.git
cd angola-news-pipeline
```

### 2. 安装依赖

```bash
# Python 3.9+ 推荐
pip3 install -r requirements.txt

# 如果使用 browser 模式，还需要安装 agent-browser
npm install -g agent-browser
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，并填入您的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env`，填入以下内容：

```env
GEMINI_API_KEY=your_gemini_api_key
ZHIPU_API_KEY=your_zhipu_api_key
ANTHROPIC_AUTH_TOKEN=your_anthropic_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token  # 可选
TELEGRAM_CHAT_ID=your_telegram_chat_id      # 可选
```

**获取 API 密钥：**

- **Gemini**: https://ai.google.dev (免费，推荐)
- **GLM (智谱)**: https://bigmodel.cn (免费额度)
- **Claude**: Anthropic 控制台 https://console.anthropic.com/
- **Telegram**: BotFather (@BotFather) 创建机器人

### 4. 运行流水线

完整运行（推荐）：
```bash
bash RUN_ALL.sh
```

分步运行（调试用）：
```bash
python3 scripts/01-fetch-headlines.py       # 抓取
python3 scripts/02-extract-final.py data/   # 提取 + 去重
python3 scripts/03-score-ai.py data/        # AI 评分
python3 scripts/06-translate-agent.py data/ # 翻译
python3 scripts/07-push-cn.py               # Telegram 推送
```

工具命令：
```bash
python3 scripts/03-score-ai.py --list       # 查看评分提供者状态
python3 scripts/99-cleanup.py               # 清理旧运行目录和过期记录
```

## 配置说明

### config.json

#### 新闻源配置

```json
{
  "sources": [
    {
      "name": "网站名",
      "url": "https://example.com",
      "fetch_mode": "curl",  // 或 "browser"（用于 Cloudflare/SPA）
      "patterns": [...]      // 正则提取规则
    }
  ]
}
```

**fetch_mode 说明：**
- `curl` (默认): 快速，适用大多数网站
- `browser`: 用于 Cloudflare 防护或 JavaScript 渲染网站

#### AI 评分提供者

按数组顺序自动降级，覆盖率 ≥80% 即认为成功：

```json
{
  "scoring": {
    "providers": [
      {
        "name": "gemini-flash",
        "enabled": true,
        "type": "openai-compat",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
        "api_key_env": "GEMINI_API_KEY"
      },
      {
        "name": "glm-flash",
        "enabled": true,
        "type": "openai-compat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4.7-flash",
        "batch_size": 50,
        "api_key_env": "ZHIPU_API_KEY"
      },
      {
        "name": "claude-haiku",
        "enabled": true,
        "type": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "api_key_env": "ANTHROPIC_AUTH_TOKEN"
      },
      {
        "name": "keyword",
        "enabled": true,
        "type": "keyword"
      }
    ]
  }
}
```

**支持的 type：**
- `openai-compat`: OpenAI 兼容接口（Gemini、GLM 等）
- `anthropic`: Anthropic 原生接口
- `keyword`: 关键词评分（兜底，无需 API）

## 数据流

```
抓取 → 提取+去重 → AI评分 → 翻译 → Telegram推送
```

| 步骤 | 输入 | 输出 | 文件 |
|------|------|------|------|
| 抓取 | 18 个新闻源 | HTML | `data/runs/YYYY-MM-DD/html/` |
| 提取 | HTML + articles-db.json | 增量新文章 | `delta-new.json` |
| 评分 | 新文章 | 筛选结果 (≥5分) | `filtered-candidates.json` |
| 翻译 | 筛选文章 | 中文标题 | `translated-headlines.json` |
| 推送 | 中文新闻 | Telegram 消息 | 消息 ID + DB 更新 |

## 增量去重机制

- `data/articles-db.json`: 存储所有文章 SHA-256 URL 哈希（前 16 位）
- 提取阶段对比数据库，只输出全新文章
- 已存在文章仅更新 `lastSeen` 时间戳
- 超过 30 天的记录自动清理

## 定时运行（GitHub Actions）

创建 `.github/workflows/daily-news.yml`：

```yaml
name: Daily Angola News Pipeline

on:
  schedule:
    - cron: '0 8 * * *'  # 每天 08:00 UTC 运行
  workflow_dispatch:      # 支持手动触发

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          npm install -g agent-browser

      - name: Create .env
        run: |
          echo "GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }}" >> .env
          echo "ZHIPU_API_KEY=${{ secrets.ZHIPU_API_KEY }}" >> .env
          echo "ANTHROPIC_AUTH_TOKEN=${{ secrets.ANTHROPIC_AUTH_TOKEN }}" >> .env
          echo "TELEGRAM_BOT_TOKEN=${{ secrets.TELEGRAM_BOT_TOKEN }}" >> .env
          echo "TELEGRAM_CHAT_ID=${{ secrets.TELEGRAM_CHAT_ID }}" >> .env

      - name: Run pipeline
        run: bash RUN_ALL.sh

      - name: Commit and push updates
        run: |
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"
          git add data/articles-db.json data/sent-history.json
          git commit -m "chore: update article database and history" || true
          git push
```

**在 GitHub 设置 Secrets：**

1. 进入 Settings → Secrets and variables → Actions
2. 添加以下 secrets:
   - `GEMINI_API_KEY`
   - `ZHIPU_API_KEY`
   - `ANTHROPIC_AUTH_TOKEN`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

## 故障排查

### browser 模式超时

设置环境变量：
```bash
export AGENT_BROWSER_DEFAULT_TIMEOUT=60000
```

### API 限流

调整 `config.json` 中的 `batch_size`（推荐 50 以下）。

### 翻译失败

- 检查 uapis.cn 可用性
- 调整 `scripts/06-translate-agent.py` 中的 `BATCH_SIZE`

## 开发指南

详见 [CLAUDE.md](./CLAUDE.md) 了解：
- 项目架构设计
- 添加新的新闻源
- 添加新的 AI 评分提供者
- 性能优化建议

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 📧 Email: your-email@example.com
- 🐦 Twitter: @yourhandle
- 💬 Telegram: @yourchannel
