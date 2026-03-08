#!/bin/bash
# 安哥拉新闻流水线 - 完整流程（增量处理版）

set -euo pipefail

# 动态获取脚本所在目录（支持本地和 GitHub Actions）
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "📰 安哥拉新闻流水线 - 增量处理版"
echo "================================"
echo ""

# 步骤0: 清理旧数据
echo "📋 步骤0: 清理旧运行目录和过期记录..."
python3 scripts/99-cleanup.py
echo ""

# 步骤1: 抓取新闻
echo "📋 步骤1: 抓取新闻..."
python3 scripts/01-fetch-headlines.py
echo ""

# 步骤2: 提取标题和链接（与数据库对比，输出增量）
echo "📋 步骤2: 提取标题和链接（增量对比）..."
python3 scripts/02-extract-final.py
echo ""

# 检查增量是否为 0，提前退出节省 API 调用
RUN_DIR=$(cat data/.current-run)
DELTA_FILE="$RUN_DIR/delta-new.json"
if [ -f "$DELTA_FILE" ]; then
    NEW_COUNT=$(python3 -c "import json; print(json.load(open('$DELTA_FILE')).get('total_new', 0))")
    if [ "$NEW_COUNT" -eq 0 ]; then
        echo "ℹ️  没有新文章，跳过后续步骤"
        echo "✅ 流程完成（无新内容）"
        exit 0
    fi
    echo "📊 发现 $NEW_COUNT 篇新文章，继续处理..."
    echo ""
fi

# 步骤3: AI 评分筛选（Claude Haiku 批量评分，替代关键词匹配）
echo "📋 步骤3: AI 评分筛选（分数>=5）..."
python3 scripts/03-score-ai.py
echo ""

# 检查筛选结果
FILTERED_FILE="$RUN_DIR/filtered-candidates.json"
if [ -f "$FILTERED_FILE" ]; then
    FILTERED_COUNT=$(python3 -c "import json; print(json.load(open('$FILTERED_FILE')).get('total_filtered', 0))")
    if [ "$FILTERED_COUNT" -eq 0 ]; then
        echo "ℹ️  没有高分文章，跳过翻译和推送"
        echo "✅ 流程完成（无高分内容）"
        exit 0
    fi
fi

# 步骤4: 翻译成中文
echo "📋 步骤4: 翻译成中文..."
python3 scripts/06-translate-agent.py
echo ""

# 步骤5: 推送到Telegram
echo "📋 步骤5: 推送到 Telegram..."
python3 scripts/07-push-cn.py
echo ""

echo "✅ 流程完成！"
