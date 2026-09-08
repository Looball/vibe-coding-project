# CLAUDE.md

VibeQA —— 基于 RAG + Milvus + 阿里云 DashScope 的智能问答系统（FastAPI / Python 3.12，uv 管理）。

配套 PRD 与技术设计见 `documents/data/product_requirement_document.md`、`documents/data/technical_design_document.md`。所有非敏感配置以 `documents/data/config.ini` 为唯一权威来源（可用环境变量 `EDURAG_CONFIG` 覆盖路径）；敏感密钥只放 `.env`（`DASHSCOPE_API_KEY`）。

## Startup Workflow

Before writing code:

1. **确认工作目录**：`pwd` 必须在 `/Users/bing/Desktop/Github/vibe-coding`
2. **读本文件**（本文）与 `progress.md`、`feature_list.json`
3. **读项目文档**：`documents/data/` 下的 PRD / TDD
4. **运行 `./init.sh`** 验证环境健康；若基线失败先修复，再谈新功能
5. **检查本地服务**：MySQL(3306) / Redis(6379) / Milvus(19530) 是否在 docker 中运行（见下）
6. 注意：本目录**不是 git 仓库**，提交/回滚类命令不可用，变更前先备份

## Working Rules

- **One feature at a time**：一次只做一件事，从 `feature_list.json` 选一个未完成 feature
- **验证必跑**：未跑验证命令不得声称完成（先跑 `./init.sh`，功能级另跑第 5 步依赖的烟测）
- **更新产物**：结束前更新 `progress.md` 与 `feature_list.json`，记录验证证据
- **不越界**：不改与当前 feature 无关的文件
- **环境命令**：依赖用 `uv add <pkg>` / `uv sync`，执行用 `uv run python ...`，不要直接调用宿主 `python3`（会漏掉 `.venv` 依赖）
- **敏感信息**：`DASHSCOPE_API_KEY` 只写 `.env`，日志/提交/回复中不得明文展示 key

## Runtime Dependencies (docker-compose)

| 服务 | 端口 | 项目目录 | 说明 |
|---|---|---|---|
| MySQL | 3306 | `~/Desktop/Github/MySQL` | 库 `VibeQA`（config 指定），root/mysqlroot |
| Redis | 6379 | `~/Desktop/Github/Redis` | 密码 `redispass` |
| Milvus | 19530 | `~/Desktop/Github/Milvus` | 库 `VibeQA`、collection `RAGQA` |

服务停止时按需拉起：`cd <项目目录> && docker compose up -d`。Milvus 就绪以 `curl -sf http://localhost:9091/healthz` 为准（需 30~90s）。

## Architecture Map

- `app/core/config.py` —— 解析 config.ini → `Settings`（dataclass）
- `app/db/{mysql,redis,milvus}.py` —— 各存储 client（MilvusStore 含建集/写向量/检索/删除）
- `app/models/mysql_models.py` —— SQLAlchemy ORM 表模型（subjects/documents/conversations/messages/knowledge_points）
- `app/clients/dashscope.py` —— 阿里云 DashScope（LLM 对话+流式、text-embedding-v3 嵌入）
- `app/rag/` —— 检索增强链路（document_loader/chunker/待补 retriever）
- `app/services/` —— 业务编排（ingestion 等）
- `app/api/`、`main.py` —— FastAPI 入口与路由

## Required Artifacts

- `feature_list.json` —— feature 状态追踪（唯一事实源）
- `progress.md` —— 会话连续性日志
- `init.sh` —— 标准启动与验证路径
- `session-handoff.md` —— 跨会话交接

## Definition of Done

一个 feature 只有在以下**全部**满足时才可标记完成：

- [ ] 目标行为已实现
- [ ] 验证确实运行过（`./init.sh` + 该功能对应的烟测命令），且有命令输出作证据
- [ ] 证据写入 `feature_list.json` / `progress.md`
- [ ] 仓库可再次从标准启动路径 `./init.sh` 直接拉起

## Verification Commands

```bash
# 完整验证（推荐）
./init.sh
```

功能级烟测示例（uv 环境）：
- 全量语法：`uv run python -m compileall -q app main.py`
- 导入链：`uv run python -c "import app; app.create_app()"`
- pytest 用例（写好后跑）：`uv run pytest -q`
- MySQL 连通：`uv run python -c "from app.db import mysql; print(mysql.ping())"`
- Milvus 连通/建集：`uv run python -c "from app.db import milvus; milvus.get_store().ensure_collection()"`
- 配置解析：`uv run python -c "from app.core.config import settings; print(settings.mysql_database, settings.milvus_collection)"`

## End of Session

Before ending a session:

1. 更新 `progress.md`（Current State / What's In Progress / Next / Blockers）
2. 更新 `feature_list.json` 的 feature 状态与 evidence
3. 在 `session-handoff.md` 记录验证证据、改动文件、未解决问题
4. 记录风险与推荐下一步
5. 保证仓库可随时从 `./init.sh` 干净拉起

## Escalation

- **架构决策**：先查 TDD，否则问用户
- **需求不清**：先查 PRD，否则问用户
- **环境问题**（服务未启动/凭据不符）：服务启动属 docker 本地可逆操作可自行执行；数据库账号密码等凭据不一致时先与用户核对，不猜测不改 config.ini
- **连续失败**：更新 `progress.md` 并交由人工复核
- **范围模糊**：重读 `feature_list.json` 的完成定义
