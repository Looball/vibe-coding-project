# CLAUDE.md

VibeQA —— 基于 RAG + Milvus 混合检索的 IT 学习智能问答系统（FastAPI / Python 3.12，uv 管理，前后端分离）。

配套 PRD 与技术设计见 `documents/data/`。配置分层：
- 非敏感基础设施/检索参数 → `documents/data/config.ini`（可用 `EDURAG_CONFIG` 覆盖路径）
- 服务商与模型（可选覆盖）→ `.env`：`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`LLM_MODEL`、`EMBEDDING_MODEL`
- 密钥只放 `.env`，勿入 git（`.env` 已被 gitignore）

当前服务商为 SiliconFlow（OpenAI 兼容）：LLM=`deepseek-ai/DeepSeek-V4-Flash`，嵌入=`BAAI/bge-m3`(dense 1024)；sparse 词法路由 Milvus 服务端 **BM25 FUNCTION（jieba analyzer）**，与 dense 组成混合检索 + RRF。

## Startup Workflow

Before writing code:

1. **确认工作目录**：`pwd` 必须在 `/Users/bing/Desktop/Github/vibe-coding`
2. **读本文件**（本文）与 `progress.md`、`feature_list.json`
3. **读项目文档**：`documents/data/` 下的 PRD / TDD
4. **运行 `./init.sh`** 验证环境健康（语法/导入/pytest/config/服务探测）；基线失败先修再开工
5. **检查本地服务**：MySQL(3306) / Redis(6379) / Milvus(19530) 是否在 docker 中运行（见下）
6. **git**：本目录为 git 仓库(main)。破坏性 git 操作前先 `git status`；功能完成、用户示意后再 commit

## Working Rules

- **One feature at a time**：一次只做一件事，从 `feature_list.json` 选一个未完成 feature（当前已全部完成，新需求需新增 feature 条目）
- **验证必跑**：未跑验证不得声称完成（`./init.sh` + 对应功能烟测）
- **更新产物**：结束前更新 `progress.md` 与 `feature_list.json`，记录验证证据
- **不越界**：不改与当前 feature 无关的文件
- **环境命令**：依赖 `uv add <pkg>` / `uv sync`，执行 `uv run python ...`；勿用宿主 `python3`（宿主 3.14 ≠ 项目 .venv 3.12）
- **敏感信息**：provider key 只在 `.env`，日志/提交/回复中不得明文展示
- **提交**：用户说"提交"时再 commit；commit 前 `git status` 复核无敏感文件

## Runtime Dependencies (docker-compose)

| 服务 | 端口 | 项目目录 | 说明 |
|---|---|---|---|
| MySQL | 3306 | `~/Desktop/Github/MySQL` | 库 `VibeQA`（config 指定），root/mysqlroot |
| Redis | 6379 | `~/Desktop/Github/Redis` | 密码 `redispass` |
| Milvus | 19530 | `~/Desktop/Github/Milvus` | 库 `VibeQA`、collection `RAGQA`；需支持 BM25 FUNCTION/jieba analyzer 的版本 |

服务停止时：`cd <项目目录> && docker compose up -d`。Milvus 就绪判据 `curl -sf http://localhost:9091/healthz`（30~90s）。

## Architecture Map

- `app/core/config.py` —— 解析 config.ini → `Settings`，并应用 `.env` 对 base_url/LLM/嵌入模型的覆盖
- `app/db/{mysql,redis,milvus}.py` —— 存储 client；MilvusStore 为 **hybrid schema**（dense + BM25/sparse），含 `hybrid_search`(RRF)/`flush`/建集/删除
- `app/models/mysql_models.py` —— ORM 表模型（subjects/documents/conversations/messages/knowledge_points）
- `app/clients/dashscope.py` —— 模型 client（LLM 即时/流式 + 嵌入，指向 `.env` 指定的 OpenAI 兼容服务商）
- `app/rag/` —— document_loader / chunker(Parent-Child) / retriever(混合检索+父块去重) / greeting / query_rewrite(LLM) / **pipeline(RAG 流程编排)**
- `app/services/` —— qa(基于 pipeline 的问答薄层) / ingestion(语料入库)
- `app/api/` —— FastAPI 路由：chat(即时+SSE)、conversations、meta(subjects/health)；默认不托管前端
- `frontend/` —— 原生 SPA（学科/会话/即时+流式问答），独立静态服务
- `main.py` —— uvicorn 入口

## Required Artifacts

- `feature_list.json` —— feature 状态追踪（唯一事实源）
- `progress.md` —— 会话进度日志（每轮 Session 一条，最新在上）
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
- pytest 单测（离线）：`uv run python -m pytest -q`
- pytest 集成（需本地服务）：`uv run python -m pytest -m integration -q`
- MySQL 连通：`uv run python -c "from app.db import mysql; print(mysql.ping())"`
- Milvus 建集/检索：`uv run python -c "from app.db import milvus; milvus.get_store().ensure_collection()"`
- 配置自检：`uv run python -c "from app.core.config import settings; print(settings.mysql_database, settings.milvus_collection, settings.embedding_model)"`
- RAG 流程演示：`uv run python -m app.rag.pipeline "什么是大语言模型" --subject ai`

## End of Session

Before ending a session:

1. 更新 `progress.md`（新增/更新当前 Session：What / 验证证据 / Blockers / 下一步）
2. 更新 `feature_list.json` 的 feature 状态与 evidence
3. 在 `session-handoff.md` 记录验证证据、改动文件、未解决问题
4. 记录风险与推荐下一步
5. 保证仓库可随时从 `./init.sh` 干净拉起

## Escalation

- **架构决策**：先查 TDD，否则问用户
- **需求不清**：先查 PRD，否则问用户
- **环境问题**（服务未启动/凭据不符）：服务启动属 docker 本地可逆操作可自行执行；provider key 失效或服务商/模型切换，与用户核对 `.env`，不猜测不自行造 key
- **Milvus schema 变更**：涉及 BM25/sparse 或维度变化时需 drop 重建 + `ingestion --reset` 重入库（会重新在线嵌入）
- **连续失败**：更新 `progress.md` 并交由人工复核
- **范围模糊**：重读 `feature_list.json` 的完成定义
