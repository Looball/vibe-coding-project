#!/bin/bash
# VibeQA 标准启动与验证脚本（uv 环境）
# 用途：语法/导入/配置基线；服务可用性仅提示，不作为失败条件（让无服务的静态工作也能过）。
set -e

echo "=== VibeQA Harness Initialization ==="

# 1) 工具链
command -v uv >/dev/null 2>&1 || { echo "缺少 uv，请先安装 (curl -LsSf https://astral.sh/uv/install.sh | sh)"; exit 1; }
echo "uv: $(uv --version)"

# 2) 依赖同步（幂等，快）
echo "=== uv sync ==="
uv sync --quiet

# 3) 语法基线
echo "=== compileall ==="
uv run python -m compileall -q app main.py

# 4) 导入与 app 工厂（不需要外部服务）
echo "=== import / create_app ==="
uv run python -c "import app; app.create_app(); print('create_app OK')"

# 4b) pytest（有 tests 目录才跑）
echo "=== pytest (if present) ==="
if [ -d tests ]; then
  uv run python -m pytest -q
else
  echo "tests 目录不存在，跳过（暂无单元测试）"
fi

# 5) 配置解析自检（输出当前目标库/集合，便于人工核对 config.ini）
echo "=== config self-check ==="
uv run python -c "from app.core.config import settings; print('mysql_db =', settings.mysql_database); print('milvus_collection =', settings.milvus_collection)"

# 6) 运行时服务探测（仅提示）
echo "=== runtime services (informational) ==="
for spec in "3306:MySQL" "6379:Redis" "19530:Milvus"; do
  port="${spec%%:*}"; name="${spec##*:}"
  if nc -z -w1 127.0.0.1 "$port" >/dev/null 2>&1; then
    echo "  $name(port $port): UP"
  else
    echo "  $name(port $port): DOWN (不影响以上静态检查)"
  fi
done

echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Read feature_list.json to see current feature state"
echo "2. Pick ONE unfinished feature to work on"
echo "3. Implement only that feature"
echo "4. Re-run verification before claiming done"
