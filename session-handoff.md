# Session Handoff

## Current Objective

- Goal: 上一目标 feat-004 语料入库已达成（ai_data 2 文档 → 70 子块 → VibeQA/RAGQA；MySQL subjects 5 + documents 2）。下一目标 = feat-005 检索编排与 RAG 问答。
- Current status: feat-004 收尾验证通过（E2E 检索命中 LLM 相关父块）
- Branch / commit: main @ 8cff070（首次提交）

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

- 开工 feat-005（检索编排/RAG 问答）：milvus `search()` 命中按 `parent_chunk_id` 去重聚合取 Top `candidate_m`，拼 TDD 5.2 模板 prompt → `dashscope.chat`/`achat_stream` 生成。上一 session 已把语料（70 子块）入库 VibeQA/RAGQA 并验证检索可用。
