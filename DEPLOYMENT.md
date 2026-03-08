# 定时任务配置指南

本项目支持两种运行环境：**本地系统 cron** 和 **GitHub Actions**。脚本已重构为环境无关，路径由脚本动态确定。

## 路径解决方案

### 技术实现

脚本已修改为使用相对路径，而不是硬编码的绝对路径：

**bash (RUN_ALL.sh):**
```bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

**Python (scripts/utils.py):**
```python
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)  # 向上一级到项目根目录
```

这样无论脚本在哪里运行，都能正确定位项目根目录。

## 本地 Cron 配置

### 1. 配置 .env 文件

```bash
cp .env.example .env
# 编辑 .env，填入 API 密钥
nano .env
```

### 2. 测试脚本可运行性

```bash
# 从任意目录运行脚本（验证相对路径有效）
cd /tmp
bash /home/jd/.openclaw/workspace/angola-news-pipeline/RUN_ALL.sh

# 或
cd /home
bash /home/jd/.openclaw/workspace/angola-news-pipeline/RUN_ALL.sh
```

### 3. 添加 Cron 任务

编辑 crontab：
```bash
crontab -e
```

添加定时任务（每天 08:00 UTC）：
```cron
# 安哥拉新闻流水线 - 每日 08:00 UTC
0 8 * * * cd /home/jd/.openclaw/workspace/angola-news-pipeline && bash RUN_ALL.sh >> /tmp/angola-news-pipeline.log 2>&1
```

**或** 直接指定完整路径（不需要 cd）：
```cron
0 8 * * * /home/jd/.openclaw/workspace/angola-news-pipeline/RUN_ALL.sh >> /tmp/angola-news-pipeline.log 2>&1
```

### 4. 验证 Cron 运行

```bash
# 查看日志
tail -f /tmp/angola-news-pipeline.log

# 手动测试 cron 环境（模拟 cron 的稀疏环境变量）
env -i HOME=$HOME /bin/bash -c 'cd /home/jd/.openclaw/workspace/angola-news-pipeline && bash RUN_ALL.sh'
```

## GitHub Actions 配置

GitHub Actions 工作流已预置在 `.github/workflows/daily-news.yml` 中。

### 1. 设置 Repository Secrets

进入 GitHub 仓库 → Settings → Secrets and variables → Actions

添加以下 secrets:
- `GEMINI_API_KEY` - Google Gemini API 密钥
- `ZHIPU_API_KEY` - GLM/智谱 API 密钥
- `ANTHROPIC_AUTH_TOKEN` - Anthropic/Claude API 密钥
- `TELEGRAM_BOT_TOKEN` (可选) - Telegram 机器人 token
- `TELEGRAM_CHAT_ID` (可选) - Telegram 频道 ID

### 2. 工作流说明

工作流配置：
```yaml
on:
  schedule:
    - cron: '0 8 * * *'  # 每天 08:00 UTC
  workflow_dispatch:     # 支持手动触发
```

**工作流步骤：**
1. 检出代码
2. 安装 Python 和 Node.js 依赖
3. 创建 `.env` 文件（从 secrets）
4. 运行 `bash RUN_ALL.sh`
5. 自动提交数据库更新（articles-db.json, sent-history.json）
6. 失败时上传日志

### 3. 手动触发工作流

GitHub 网页界面 → Actions → Daily Angola News Pipeline → Run workflow

或使用 GitHub CLI：
```bash
gh workflow run daily-news.yml --repo jinde98/angola-news-pipeline
```

## 两环境兼容性验证清单

- [x] **相对路径**: 脚本使用相对于自身位置的路径查找项目根目录
- [x] **动态路径**: 无硬编码的绝对路径（除了日志输出）
- [x] **环境变量**: 从 `.env` 文件读取，支持本地和 GitHub Secrets
- [x] **数据持久化**:
  - `data/articles-db.json` 在本地和 GitHub 上都同步更新
  - `data/sent-history.json` 通过 git 提交保持一致
- [x] **依赖**:
  - Python 库：pip install -r requirements.txt
  - Node.js 库：npm install -g agent-browser
- [x] **网络访问**:
  - 本地：无限制
  - GitHub Actions: 标准互联网访问（可能受限某些特定 IP）

## 故障排查

### 本地 Cron 无法运行

**问题**: Cron 输出为空或报错

**排查步骤**:
```bash
# 1. 验证脚本可直接运行
bash /home/jd/.openclaw/workspace/angola-news-pipeline/RUN_ALL.sh

# 2. 检查 crontab 权限
ls -la /var/spool/cron/crontabs/

# 3. 查看 cron 日志
sudo tail -f /var/log/cron  # CentOS/RHEL
# 或
sudo tail -f /var/log/syslog | grep CRON  # Ubuntu/Debian

# 4. 测试 cron 环境
env -i HOME=$HOME /bin/bash -l -c 'bash /home/jd/.openclaw/workspace/angola-news-pipeline/RUN_ALL.sh'
```

### GitHub Actions 失败

**问题**: Workflow 运行失败

**排查步骤**:
1. 进入 Actions → 最新运行 → 查看详细日志
2. 检查 Secrets 是否正确设置（Settings → Secrets）
3. 检查网络连接（uapis.cn, API 服务可用性）
4. 查看生成的 artifacts（失败时会上传日志）

### API 限流

**问题**: Gemini/GLM/Claude API 返回限流错误

**解决方案**:
- 检查 API 账户的使用额度
- 调整 `config.json` 中的 `batch_size` (推荐 50 以下)
- 增加提供者之间的时间延迟

## 环境变量一览表

| 变量 | 本地 cron | GitHub Actions | 说明 |
|------|---------|-----------------|------|
| `GEMINI_API_KEY` | `.env` | Secrets | Google Gemini API |
| `ZHIPU_API_KEY` | `.env` | Secrets | GLM/智谱 API |
| `ANTHROPIC_AUTH_TOKEN` | `.env` | Secrets | Claude API |
| `TELEGRAM_BOT_TOKEN` | `.env` | Secrets (可选) | Telegram 推送 |
| `TELEGRAM_CHAT_ID` | `.env` | Secrets (可选) | Telegram 频道 |
| `AGENT_BROWSER_DEFAULT_TIMEOUT` | 自动 (60000) | 自动 (60000) | Browser 超时 |

## 最佳实践

### 安全性
- **不要提交 `.env` 文件** 到 Git
- **定期轮换 API 密钥**
- **在 GitHub 上使用 Secrets，不要在工作流中硬编码**

### 可靠性
- **本地验证**: 修改脚本后，先在本地测试运行
- **日志监控**: 定期检查 `/tmp/angola-news-pipeline.log`
- **数据备份**: 定期备份 `data/articles-db.json` 和 `data/sent-history.json`

### 性能
- **批处理**: 调整 `batch_size` 以平衡 API 调用和响应时间
- **缓存**: 增量处理机制避免重复处理
- **清理**: 定期运行 `python3 scripts/99-cleanup.py` 清理过期数据

## 参考

- [Cron 表达式格式](https://crontab.guru/)
- [GitHub Actions 计划事件](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [GitHub Secrets 管理](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
