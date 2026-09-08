# Session Handoff

## Current Objective

- Goal: 完成 feat-004 语料入库 —— 把 `documents/data/ai_data` 解析→Parent-Child 分块→DashScope 嵌入→写入 Milvus(RAGQA) 并同步 MySQL
- Current status: 环境与前置模块全部就绪，只差 chunker/ingestion 代码与执行；本会话应 `/harness-creator` 暂停了入库，先建了项目 harness
- Branch / commit: 非 git 仓库，无分支

## Completed This Session

- [x] 本会话启动 Milvus（etcd+standalone），MySQL 建库 `VibeQA`，Python 端连通与建集验证通过
- [x] 生成 5 个 harness 文件（CLAUDE.md / feature_list.json / progress.md / session-handoff.md / init.sh）
- [x] 写 `app/rag/document_loader.py`（PDF/DOCX 按页抽取）

## Verification Evidence

| Check | Command | Result | Notes |
|---|---|---|---|
| 语法 | `uv run python -m compileall -q app main.py` | PASS | |
| 导入/建 app | `uv run python -c "import app; app.create_app()"` | PASS | 需 `DASHSCOPE_API_KEY` 非空 |
| MySQL 连通 | `uv run python -c "from app.db import mysql; print(mysql.ping())"` | PASS | True |
| Milvus 建集 | `uv run python -c "from app.db import milvus; milvus.get_store().ensure_collection()"` | PASS | has_collection=True, db=VibeQA, collection=RAGQA |
| 配置解析 | `uv run python -c "from app.core.config import settings; print(settings.mysql_database, settings.milvus_collection)"` | PASS | VibeQA / RAGQA |

## Files Changed

- 新建：`CLAUDE.md`、`feature_list.json`、`progress.md`、`session-handoff.md`、`init.sh`、`app/rag/document_loader.py`
- 修改：`app/core/config.py`（改为读 config.ini）、`app/db/milvus.py`（Schema 增 parent_text/doc_title/page）、`pyproject.toml`/`uv.lock`（+pypdf/python-docx/tiktoken）

## Decisions Made

- 配置唯一权威 = `documents/data/config.ini`；`.env` 只放 `DASHSCOPE_API_KEY`
- Milvus 单 collection：子块向量 + 每行冗余父块文本 `parent_text`，免父子二次查询
- 执行命令一律 `uv run python`，禁用宿主 `python3`

## Blockers / Risks

- 无硬阻塞。嵌入为在线 API 调用（text-embedding-v3），会按量计费；重跑需先 `--reset` 防重复向量
- 宿主 python3(3.14) ≠ 项目 .venv(3.12)，勿混用

## Next Session Startup

1. Read `CLAUDE.md`.
2. Read `feature_list.json` and `progress.md`.
3. Review this handoff.
4. Run `./init.sh` or the documented verification command before editing.

## Recommended Next Step

- 写 `app/rag/chunker.py` 与 `app/services/ingestion.py`，提供 `python -m app.services.ingestion --dir documents/data/ai_data --subject ai` 入口；`init_db()` 建表 + 种子 subjects 后入库，最后核对 MySQL 行数与 Milvus 实体数。
