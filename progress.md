# 进度日志

这是一个通用的仓库内会话进度日志。claude-progress.md 只是课程沿用的历史文件名，并不要求使用 Claude Code。只要仓库里的指令明确要求，Codex 或其他 coding agent 都可以在开工时读取、交接前更新；agent 不会自动维护这个文件。

## 当前已验证状态

- 仓库根目录：`/Users/bing/Desktop/Github/vibe-coding`
- 标准启动路径：`./init.sh`（uv sync → 语法/导入/配置自检）；运行时依赖 docker 服务：MySQL:3306、Redis:6379、Milvus:19530（拉起见 `CLAUDE.md`）
- 标准验证路径：`./init.sh` + 功能烟测 `uv run python ...`（详见 `CLAUDE.md` Verification Commands）
- 当前最高优先级未完成功能：无（feat-001~008 已全部完成；后续为新增需求/前端等扩展）
- 当前 blocker：无硬阻塞。注意——在线嵌入/LLM 按量计费；宿主 `python3`(3.14) ≠ 项目 `.venv`(3.12)，命令统一 `uv run python`

## 会话记录

### Session 001

- 日期：2026-09-08
- 本轮目标：从 PRD 产出技术设计文档；用 uv 建 Python 项目骨架；基于 config.ini 生成配置中心与 MySQL/Milvus/Redis/模型 client
- 已完成：
  - `documents/data/technical_design_document.md`（RAG + Milvus + 阿里云 DashScope，Parent-Child 1200/300/50）
  - `uv venv`(py3.12) + `pyproject.toml`/`uv.lock`；FastAPI 骨架 `app/{core,db,models,clients,rag,services}`
  - 配置中心解析 config.ini；`.env` 仅承载 `DASHSCOPE_API_KEY`
  - MySQL(SQLAlchemy+PyMySQL)/Redis/Milvus client 与 ORM 表模型（subjects/documents/conversations/messages/knowledge_points）
  - DashScope client：LLM 即时/同步流/异步流 + `text-embedding-v3` 嵌入
- 运行过的验证：`uv run python -m compileall -q app main.py` PASS；config 解析正确；导入链与 `create_app()` OK
- 已记录证据：client 模块导入、Milvus schema 离线构建、DashScope 实例化均通过
- 提交记录：无（变更在 Session 002 首次提交一并纳入）
- 更新过的文件或工件：`documents/data/technical_design_document.md`、`pyproject.toml`/`uv.lock`、`app/*`、`main.py`
- 已知风险或未解决问题：config.ini 当时未指向可用库/凭据（后续由 Session 003 环境就绪解决，配置改为 VibeQA）
- 下一步最佳动作：推进环境就绪与语料入库

### Session 002

- 日期：2026-09-08
- 本轮目标：建立项目 harness（agent 协作基线）；git 初始化并首次提交
- 已完成：
  - `/harness-creator` 生成 `CLAUDE.md` / `feature_list.json` / `progress.md` / `session-handoff.md` / `init.sh`（validate 100/100）
  - `.gitignore` 排除 `.env`、`config.ini`、`documents/data/ai_data/`；`git init -b main`；首次提交
- 运行过的验证：`node .../validate-harness.mjs` → 100/100；`./init.sh` 全流程通过（uv sync→compileall→import→config→服务探测）
- 已记录证据：`init.sh` 输出与 `validate-harness.mjs` 报告
- 提交记录：`8cff070` chore: 初始化 VibeQA RAG 智能问答系统项目（27 files / +3558）
- 更新过的文件或工件：`CLAUDE.md`、`feature_list.json`、`progress.md`、`session-handoff.md`、`init.sh`、`.gitignore`
- 已知风险或未解决问题：本目录早期非 git 仓库，无版本回退；敏感/语料文件已入忽略清单
- 下一步最佳动作：衔接 Session 003 完成语料入库

### Session 003

- 日期：2026-09-08
- 本轮目标：feat-004 语料入库——`documents/data/ai_data` → Parent-Child 分块 → DashScope 嵌入 → Milvus `VibeQA/RAGQA` + MySQL 记录
- 已完成：
  - 环境就绪：启动 Milvus（etcd+standalone）；MySQL 建库 `VibeQA`；Milvus schema 增 `parent_text`/`doc_title`/`page` 并重建（含 `drop_collection`）
  - `app/rag/chunker.py`（父 1200/子 300/overlap 50）+ `app/services/ingestion.py`（嵌入自适应分批、`--reset`/`--dry-run`）；`document_loader.py` 实跑
  - 入库结果：2 文档（pdf 11 页 + docx 大纲）→ 70 子块；MySQL subjects=5、documents=2（chunk_count 32+38）；Milvus row_count=70（flush 后）
- 运行过的验证：compileall PASS；`mysql.ping()` True；`ensure_collection()` 后 has_collection True；E2E 检索「什么是大语言模型」命中 LLM 相关父块 score≈0.76
- 已记录证据：MySQL/Milvus 行数与计数输出、检索烟测输出
- 提交记录：`c0a107e` feat: feat-004 语料入库完成
- 更新过的文件或工件：`app/rag/{chunker,document_loader}.py`、`app/services/ingestion.py`、`app/db/milvus.py`、`feature_list.json`（feat-004 completed）、`progress.md`
- 已知风险或未解决问题：
  - Milvus `get_collection_stats` 未 flush 时为 0，核对行数需先 `client.flush`
  - 重跑入库需 `--reset` 防重复向量；在线嵌入/LLM 按量计费
- 下一步最佳动作：开工 `feat-005` 检索编排与 RAG 问答——Milvus `search()` 命中按 `parent_chunk_id` 去重聚合、取 Top `candidate_m`，拼 TDD 5.2 模板 prompt → `dashscope.chat`/`achat_stream` 生成；完成后提交本会话变更并新增 Session 004 条目

### Session 004

- 日期：2026-09-08
- 本轮目标：feat-005 检索编排与 RAG 问答（接 Session 003 推荐），并把 Session 003 提交记录补进日志
- 已完成：
  - `app/rag/retriever.py`：query 向量化 → Milvus 检索 → 按 `parent_chunk_id` 去重取最高子分 → Top `candidate_m` 父块；`format_context` 拼带出处文本
  - `app/rag/greeting.py`：问候/致谢/道别启发式识别
  - `app/services/qa.py`：`answer_sync()`（即时）与 `answer_stream()`（sources→token→done 事件流），学科标签系统提示 + TDD 5.2 模板；无命中时返回"暂未找到"兜底
  - progress.md 补记 Session 003 提交 `c0a107e`
- 运行过的验证：
  - 问候语「你好」→ 识别为 greeting 并返回友好回复
  - 「什么是大语言模型」(ai) → 3 父块(score≈0.76) + LLM 结构化回答且标注资料编号/页
  - 流式「什么是Scaling Law」→ 9 chunk 全量文本完整（debug 原始流验证）
  - `uv run python -m compileall -q app` PASS
- 已记录证据：上述三组输出；流式 end 处 GeneratorExit 告警属脚本退出噪音（服务端长驻 loop 无影响）
- 提交记录：`e159e96` docs: progress.md 补记 Session 003 提交记录 c0a107e（feat-005 代码变更尚未提交）
- 更新过的文件或工件：`app/rag/{retriever,greeting}.py`、`app/services/qa.py`、`feature_list.json`（feat-005 completed）、`progress.md`
- 已知风险或未解决问题：无硬阻塞。RAG 依赖在线嵌入+LLM 计费；流式已在脚本退出时有 httpcore 异步清理噪音（不影响）
- 下一步最佳动作：提交 feat-005 变更；随后开工 `feat-006` REST API 与会话（`/chat` 即时 + SSE `/chat/stream`、会话增删查、学科列表、健康检查，Redis 会话 + MySQL 持久化）

### Session 005

- 日期：2026-09-08
- 本轮目标：feat-005 收尾提交 + feat-006 REST API 与会话管理
- 已完成：
  - 提交 feat-005（`a5aa7b5`）
  - `app/api/`：schemas(pydantic) + `chat.py`(`/chat` 即时、`/chat/stream` SSE via sse-starlette) + `conversations.py`(创建/列表/历史分页/发消息持久化/清除) + `meta.py`(`/subjects`、`/health` 三服务探活)；`api/__init__.py` 聚合，`create_app` 挂 `/api/v1`（移除旧内联 health）
  - 会话用 MySQL 持久化（conversations/messages），历史按时间倒序+limit/offset 滚动
- 运行过的验证：TestClient 全绿——health 三服务 up、subjects=5、会话 CRUD(201/204)、消息持久化 2 条且倒序、SSE `sources→message→done`、真实 RAG `/chat` 返回 3 sources(score≈0.78)并带答案；空 query=422
- 已记录证据：上述 TestClient 输出
- 提交记录：`a5aa7b5` feat: feat-005 检索编排与 RAG 问答（feat-006 代码尚未提交）
- 更新过的文件或工件：`app/api/{__init__,schemas,chat,conversations,meta}.py`、`app/__init__.py`、`feature_list.json`（feat-006 completed）、`progress.md`
- 已知风险或未解决问题：SSE 事件名约定 `sources/message/done`，前端需按此消费；会话无鉴权/多用户隔离（单机单用户，后续可加）
- 下一步最佳动作：提交 feat-006 变更；随后开工 `feat-007` Verification & Docs——补 pytest（client/chunker/接口），写 README 与运行说明，确认 `./init.sh` 干净重启

### Session 006

- 日期：2026-09-08
- 本轮目标：feat-006 收尾提交 + feat-007 测试与文档
- 已完成：
  - 提交 feat-006（`e8a0383`）
  - 测试基建：dev 依赖改 `[dependency-groups]`（`uv sync` 默认装）；pytest 配置 `testpaths` + `integration` marker，默认 `addopts -m not integration` 只跑离线单测
  - 单测 `tests/{test_chunker,test_greeting,test_config,test_schemas}.py`（离线）
  - 集成测试 `tests/test_api_integration.py`（`-m integration`，需本地服务）
  - `README.md`：目录结构、快速开始、API 表、RAG 链路、测试与验证
  - 验证 `./init.sh` 干净重启（含 pytest 单元）
- 运行过的验证：`uv run python -m pytest` → 21 passed / 3 deselected；`-m integration` → 3 passed；`./init.sh` 全绿（compileall/import/pytest 21/config 自检/三服务 UP）
- 已记录证据：以上 pytest 与 init.sh 输出
- 提交记录：`e8a0383` feat: feat-006 REST API 与会话管理（feat-007 变更尚未提交）
- 更新过的文件或工件：`pyproject.toml`（dev group+pytest ini）、`uv.lock`、`tests/*`、`README.md`、`feature_list.json`（feat-007 completed）、`progress.md`
- 已知风险或未解决问题：integration 用例依赖本机服务与 config.ini 凭据，他机需先按 README 起服务；无鉴权/多用户隔离
- 下一步最佳动作：提交 feat-007 变更。此后 feature_list 无未完成项——可扩展项包括：前端页面（Vue/React）、Redis 会话缓存接线、更多学科语料入库、检索 re-rank、接口鉴权/限流

### Session 007

- 日期：2026-09-08
- 本轮目标：实现完整 RAG 核心业务流程——Query 改写 + 混合检索(sparse+dense)（feat-008）
- 已完成：
  - `app/core/config.py` 并入 `SUBJECT_LABELS`/`subject_label()`（去重 ingestion/qa 复制）
  - `app/rag/query_rewrite.py`：LLM 改写（`EDURAG_DISABLE_REWRITE=1` 可关，失败回退原文）
  - `app/db/milvus.py`：RAGQA schema 重建为**混合检索**——`chunk_text` 开 analyzer(jieba)、BM25 FUNCTION→`sparse`(SPARSE_FLOAT_VECTOR/SPARSE_INVERTED_INDEX)、保留 dense(IVF_FLAT/COSINE)；新增 `hybrid_search`(dense+BM25→RRF 融合)、`flush`
  - `app/rag/retriever.py` 改走 `hybrid_search`
  - `app/rag/pipeline.py`：RAG 流程编排（问候→改写→混合召回→父块去重重排→上下文）+ CLI 演示；`app/services/qa.py` 重写为 pipeline 薄层
  - ingestion 落库后 `flush()`（sparse 索引即时可用）；`--reset` 重建并重入库 70 子块
- 运行过的验证：
  - BM25+jieba 在服务端端到端验证（临时集 + RAGQA 实测，sparse 传文本检索正确）
  - `RAGQA` 重建后 fields 含 sparse，row_count 70
  - hybrid 真实命中：「就业课程大纲」词法路把课程大纲文档顶到第一（纯 dense 时被压后）
  - CLI 全流程演示：改写「就业课程包含哪些人工智能模块?」→ Top3 父块→LLM 引用作答
  - `uv run python -m pytest` → 27 passed / 3 deselected；`-m integration` → 3 passed
- 已记录证据：以上 hybrid 命中列表与 CLI 输出
- 提交记录：无（feat-008 变更尚未提交）
- 更新过的文件或工件：`app/core/config.py`、`app/rag/{query_rewrite,pipeline,retriever}.py`、`app/db/milvus.py`、`app/services/{qa,ingestion}.py`、`tests/test_pipeline_offline.py`、`feature_list.json`（feat-008 completed）、`progress.md`
- 已知风险或未解决问题：Milvus BM25 analyzer 需服务端支持 jieba（本机 v3.0.0 可用；他机需确认版本）；混合检索依赖 RAGQA 为重建后 schema，旧数据需 `--reset` 重入库；改写为在线 LLM 调用、增加一次延迟（可用环境变量关闭）
- 下一步最佳动作：提交 feat-008 变更；随后可提交前先 `git status` 复核。后续扩展见 Session 006 列表
