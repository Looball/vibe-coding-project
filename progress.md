# Session Progress Log

## Current State

**Last Updated:** 2026-09-08 20:05
**Session ID:** vibe-coding / harness-create
**Active Feature:** feat-004 - Document Corpus Ingestion

## Status

### What's Done

- [x] feat-001 基础与配置中心：`config.ini` 解析、`.env` 注入 `DASHSCOPE_API_KEY`、uv + FastAPI 骨架
- [x] feat-002 存储 client：MySQL/Redis/Milvus + ORM 表模型 + Milvus collection `RAGQA` 建集
- [x] feat-003 DashScope client：LLM 即时/流式 + `text-embedding-v3` 嵌入
- [x] 环境就绪：启动 Milvus(etcd+standalone)；MySQL 建库 `VibeQA`；Python 端 `mysql.ping()` 与 `ensure_collection()` 均通过
- [x] `app/rag/document_loader.py`：PDF(pypdf)/DOCX(python-docx) 按页抽取
- [x] 本会话为项目创建最小 harness（CLAUDE.md/feature_list.json/progress.md/session-handoff.md/init.sh）

### What's In Progress

- [ ] feat-004 语料入库
  - Details: 待写 `app/rag/chunker.py`（Parent-Child 1200/300/50）与 `app/services/ingestion.py`（解析→分块→DashScope 嵌入→写 Milvus + MySQL documents/subjects）
  - Blockers: 无硬阻塞；真实执行需 Milvus/MySQL 在线（当前在线）+ `.env` 真实 API key（已配置），会消耗少量嵌入 API 费用

### What's Next

1. 写 `app/rag/chunker.py`（token 窗口 + 中文句界回退，overlap=50）
2. 写 `app/services/ingestion.py`：种子 subjects → init_db 建表 → 逐文档分块/嵌入/批量写 Milvus，回填 documents 表
3. 运行入库脚本，核对 MySQL 行数与 Milvus 实体数
4. 视需要跑一次 Milvus 检索烟测（不调 LLM）

## Blockers / Risks

- [ ] config.ini 曾在会话中被改为 VibeQA 命名空间（root/VibeQA、RAGQA）：所有代码以**当前 config.ini 内容**为准，勿回滚旧值
- [ ] 宿主 `python3`(3.14) 与项目 `.venv`(3.12) 分离：任何命令用 `uv run python`，勿直接 `python3`
- [ ] 本目录非 git 仓库：无版本回退，破坏性变更前手动备份

## Decisions Made

- **配置单一权威 = config.ini**：`documents/data/config.ini`；`.env` 只承载 `DASHSCOPE_API_KEY` 一个密钥
  - Context: 其余参数（host/账号/模型/检索）均已入 ini，避免两处漂移
  - Alternatives considered: 全部经 pydantic-settings 从 .env 读取（已弃用，因重复且易歧义）
- **Parent-Child 落库方式**：子块向量入库，父块文本冗余存于每行 `parent_text` 供检索期回取
  - Context: 单 collection 免二次查询即可还原上下文，Milvus 标量检索成本可忽略
  - Alternatives considered: 父子分两个 collection（更省存储但检索期多一跳）
- **Schema 重建**：为加 `parent_text/doc_title/page` 字段，collection 需 drop 后重建（当前为空集，无数据损失）

## Files Modified This Session

- `CLAUDE.md` - 新建 harness 主指令
- `feature_list.json` - 新建 feature 状态
- `progress.md` - 本文件
- `session-handoff.md` - 新建交接文档
- `init.sh` - 新建验证脚本
- `app/core/config.py` - 重写为解析 config.ini
- `app/db/{mysql,redis,milvus}.py` - client 实现/Schema 增字段
- `app/models/mysql_models.py` - ORM 表模型
- `app/clients/dashscope.py` - 模型 client
- `app/rag/document_loader.py` - 新建文档解析
- `pyproject.toml`/`uv.lock` - 新增 pypdf/python-docx/tiktoken

## Evidence of Completion

- [x] Tests pass: `uv run python -m compileall -q app main.py` → 通过
- [x] Type check clean: 无 TS；import 链 `uv run python -c "import app; app.create_app()"` → OK
- [x] Manual verification: `mysql.ping()=True`；`milvus.get_store().ensure_collection()` 后 `has_collection=True`；config 解析=mysql VibeQA / collection RAGQA

## Notes for Next Session

- 续写 feat-004：chunker 与 ingestion 骨架已在脑中成型，直接落地即可；写完先 `uv run python -m compileall -q app` 再跑脚本
- 入库脚本建议提供 `--subject ai`（ai_data 归属人工智能）与 `--reset`（drop 重建 collection + 清 documents 表）选项
- Milvus 就绪判据 `curl -sf localhost:9091/healthz`；MySQL 管理员 root/mysqlroot
